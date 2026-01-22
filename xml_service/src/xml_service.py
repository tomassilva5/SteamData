import grpc, logging, sys, requests, psycopg2, csv, io, queue, threading, time, os
from concurrent import futures
from pathlib import Path
from lxml import etree
from datetime import datetime
from flask import Flask, request, jsonify
from supabase import create_client

#environment configuration
AUTH_TOKEN = os.getenv("AUTH_TOKEN") 
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
BUCKET_XML_INBOX = "xml_inbox"
XSD_PATH = os.getenv("XSD_PATH", "steam_schema.xsd")  

#token security validation
if not AUTH_TOKEN:
    print("FATAL ERROR: AUTH_TOKEN not found in environment variables.")
    sys.exit(1)

#database connection settings
DATABASE_CONFIG = {
    "host": os.getenv("DB_HOST", "db"),
    "port": os.getenv("DB_PORT", "5432"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "123456789"),
    "dbname": os.getenv("DB_NAME", "db_TP3")
}

#service initializations
app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
internal_queue = queue.Queue()

#protobuf and path setup
current_dir = Path(__file__).resolve().parent
proto_path = current_dir.parent / 'proto'
sys.path.insert(0, str(proto_path))

try:
    import steam_pb2, steam_pb2_grpc
except ImportError:
    logging.error("CRITICAL: Proto files not found.")

def create_steam_xml(csv_data):
    root = etree.Element("GameComplianceReport", # root element
                         GenerationDate=datetime.now().strftime("%Y-%m-%d"), 
                         Version="2.0")
    
    config = etree.SubElement(root, "Configuration", ValidatedBy="XML_Service_Python", Requester="Processor_NodeJS")
    etree.SubElement(config, "DataSource", Name="Steam_Enriched_CSV", LastSync=datetime.now().isoformat())
    
    catalog = etree.SubElement(root, "Catalog")

    for row in csv_data:
        game = etree.SubElement(catalog, "Game", 
                                InternalID=str(row.get('InternalAppID', '0')), 
                                ReleaseYear=str(row.get('ReleaseYear', '2024')),
                                Genre=row.get('Genre', 'Action'))
        
        details = etree.SubElement(game, "ProductDetails")
        etree.SubElement(details, "Title").text = row.get('Title', 'Unknown Game')
        
        finance = etree.SubElement(game, "FinancialData")
        etree.SubElement(finance, "CurrentPrice", Currency="USD").text = row.get('PriceUSD', '0.00')
        
        popularity = etree.SubElement(game, "PopularityMetrics")
        etree.SubElement(popularity, "ReviewCount").text = row.get('ReviewCount', '0')

    return etree.tostring(root, pretty_print=True, encoding='unicode')

def validate_xml(xml_string):
    try:
        xml_doc = etree.fromstring(xml_string.encode("utf-8"))
        with open(XSD_PATH, "rb") as xsd_file:
            schema_doc = etree.parse(xsd_file)
            schema = etree.XMLSchema(schema_doc)
            schema.assertValid(xml_doc)
        return True, None
    except etree.DocumentInvalid as e:
        return False, str(e)
    except Exception as e:
        return False, str(e)

def async_db_worker():
    while True:
        task = internal_queue.get()
        if task is None: break
        req_id = task['request_id']
        filename = task['filename']
        try:
            #download and parse cloud file
            file_data = supabase.storage.from_(BUCKET_XML_INBOX).download(filename)
            stream = io.StringIO(file_data.decode("UTF-8"))
            csv_data = list(csv.DictReader(stream))
            #data validation
            valid = True
            if not csv_data:
                logging.error(f"VALIDATION ERROR: CSV is empty for file {filename}")
                valid = False       
            for row in csv_data:
                if not row.get("Title") or not row.get("Genre") or not row.get("ReleaseYear"):
                    logging.error(f"VALIDATION ERROR: Missing required fields in file {filename}")
                    valid = False
                    break
                try:
                    price = float(row.get("PriceUSD", 0))
                    if price < 0:
                        logging.error(f"VALIDATION ERROR: Negative price detected in file {filename}")
                        valid = False
                        break
                except ValueError:
                    logging.error(f"VALIDATION ERROR: Invalid price format in file {filename}")
                    valid = False
                    break

            if not valid:
                requests.post(task['webhook'], json={"request_id": req_id, "status": "ERRO_VALIDACAO"}, timeout=5)
                internal_queue.task_done()
                continue

            xml_content = create_steam_xml(csv_data)
            
            # XML schema validation
            xml_valid, xml_error = validate_xml(xml_content)
            if not xml_valid:
                logging.error(f"XML VALIDATION ERROR: {xml_error}")
                requests.post(task['webhook'], json={"request_id": req_id, "status": "XML_VALIDATION_ERROR"}, timeout=5)
                internal_queue.task_done()
                continue
            
            #native xml persistence in postgresql
            conn = psycopg2.connect(**DATABASE_CONFIG)
            cur = conn.cursor()
            cur.execute("INSERT INTO SteamData (XML_DOCUMENTO, MAPPER_VERSION) VALUES (%s, '2.0') RETURNING ID;", (xml_content,))
            db_id = cur.fetchone()[0]
            conn.commit()
            cur.close()
            conn.close()
            
            #notify processor via webhook
            requests.post(task['webhook'], json={"request_id": req_id, "status": "OK", "document_id": db_id}, timeout=5)

            logging.info(f"TASK SUCCESS: File {filename} remains in bucket for 10s inspection...")
            time.sleep(10)
            
            supabase.storage.from_(BUCKET_XML_INBOX).remove([filename])
            logging.info(f"TASK CLEANUP: Removed {filename} from cloud storage.")
            
        except Exception as e:
            logging.error(f"TASK ERROR: {str(e)}")
            requests.post(task['webhook'], json={"request_id": req_id, "status": "PERSISTENCE_ERROR"})
        
        internal_queue.task_done()

@app.route('/upload', methods=['POST']) # rest endpoint for file uploads
def handle_upload(): #file upload endpoint
    auth_header = request.headers.get('Authorization', '')
    token = auth_header.replace('Bearer ', '') if auth_header.startswith('Bearer ') else auth_header
    
    if token != AUTH_TOKEN: #simple token check
        return "Unauthorized", 401
    try:
        file = request.files['file']
        req_id = request.form.get('request_id')
        internal_filename = f"received_{req_id}.csv"
        
        #upload to bucket xml_inbox
        supabase.storage.from_(BUCKET_XML_INBOX).upload(path=internal_filename, file=file.read(), file_options={"content-type": "text/csv"})
        internal_queue.put({"filename": internal_filename, "request_id": req_id, "webhook": request.form.get('webhook_url')})
        
        return jsonify({"status": "ACCEPTED"}), 202
    except Exception as e:
        return jsonify({"status": "ERROR", "message": str(e)}), 500

class SteamCatalogServicer(steam_pb2_grpc.SteamCatalogServicer): #gRPC service implementation
    
    def GetGamesByFilter(self, request, context): 
        sql = """SELECT x.node::text FROM (SELECT XML_DOCUMENTO FROM SteamData ORDER BY ID DESC LIMIT 1) s, 
                 LATERAL XMLTABLE('//Game' PASSING s.XML_DOCUMENTO 
                 COLUMNS node XML PATH '.', g TEXT PATH '@Genre') AS x 
                 WHERE x.g = %s;"""
        return self._exec(sql, (request.filters.get("genre", ""),))

    def GetGamesByScore(self, request, context):
        sql = """SELECT x.node::text FROM (SELECT XML_DOCUMENTO FROM SteamData ORDER BY ID DESC LIMIT 1) s, 
                 LATERAL XMLTABLE('//Game' PASSING s.XML_DOCUMENTO 
                 COLUMNS node XML PATH '.', y INTEGER PATH '@ReleaseYear') AS x 
                 WHERE x.y >= %s;"""
        return self._exec(sql, (request.min_score,))

    def GetGamesByPrice(self, request, context):
        sql = """SELECT x.node::text FROM (SELECT XML_DOCUMENTO FROM SteamData ORDER BY ID DESC LIMIT 1) s, 
                 LATERAL XMLTABLE('//Game' PASSING s.XML_DOCUMENTO 
                 COLUMNS node XML PATH '.', p FLOAT PATH 'FinancialData/CurrentPrice') AS x 
                 WHERE x.p <= %s;"""
        return self._exec(sql, (request.max_usd,))

    def _exec(self, sql, params): #execute generic query on xml data
        try:
            conn = psycopg2.connect(**DATABASE_CONFIG)
            cur = conn.cursor()
            cur.execute(sql, params) #execute query with grpc parameters
            results = [row[0] for row in cur.fetchall()]
            cur.close()
            conn.close()
            return steam_pb2.GameReply(games_xml=results)
        except Exception as e:
            logging.error(f"gRPC SQL Error: {e}")
            return steam_pb2.GameReply(games_xml=[])

if __name__ == "__main__":
    threading.Thread(target=async_db_worker, daemon=True).start() #start background worker thread

    #initialize and start grpc server
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10)) #grpc server 10 threads
    steam_pb2_grpc.add_SteamCatalogServicer_to_server(SteamCatalogServicer(), server)
    server.add_insecure_port("[::]:50051")
    server.start()
    
    app.run(host='0.0.0.0', port=5000)
