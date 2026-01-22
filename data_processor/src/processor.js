const express = require('express');
const { createClient } = require('@supabase/supabase-js');
const axios = require('axios'); //requests http 
const csv = require('csv-parser');
const FormData = require('form-data');
const { Readable } = require('stream');

const SUPABASE_URL = process.env.SUPABASE_URL;
const SUPABASE_KEY = process.env.SUPABASE_KEY;
const EXCHANGE_API_KEY = process.env.EXCHANGE_API_KEY;
const AUTH_TOKEN = process.env.AUTH_TOKEN; 

const XML_SERVICE_URL = process.env.XML_SERVICE_URL || "http://xml_service:5000/upload";

//validate required environment variables
if (!AUTH_TOKEN || !SUPABASE_URL || !SUPABASE_KEY) {
    console.error("FATAL ERROR: Missing essential Environment Variables (AUTH_TOKEN, SUPABASE_URL, or SUPABASE_KEY).");
    process.exit(1); 
}

//bucket definitions used in the processing pipeline
const BUCKET_INPUT = "csv_uploads";   
const BUCKET_WORK = "work_area";     
const BUCKET_READY = "csv_ready";    

const supabase = createClient(SUPABASE_URL, SUPABASE_KEY);
const app = express();
app.use(express.json());
const pendingRequests = new Map();

//converts a json array into a csv string
function jsonToCSV(data) {
    if (!data || data.length === 0) return "";
    const headers = ["InternalAppID", "Title", "Genre", "ReleaseYear", "PriceUSD", "ReviewCount"];
    const rows = data.map(obj => [
        obj.InternalAppID, 
        `"${obj.Title.replace(/"/g, '""')}"`, 
        obj.Genre, 
        obj.ReleaseYear, 
        obj.PriceUSD, 
        obj.ReviewCount
    ].join(","));
    return [headers.join(","), ...rows].join("\n");
}

//retrieves the first valid value from multiple possible keys
function getValue(row, keys) {
    for (let key of keys) {
        if (row[key] !== undefined && row[key] !== null && row[key] !== "") {
            return row[key];
        }
    }
    return null;
}

//webhook endpoint to receive xml service callbacks
app.post('/callback', async (req, res) => {
    const { request_id, status } = req.body;
    console.log(`LOG: Webhook received | Request ID: ${request_id} | Status: ${status}`);

    if (status === 'OK' && pendingRequests.has(request_id)) {
        const { workFile, readyFile } = pendingRequests.get(request_id);
        console.log(`LOG: Cleaning temporary storage in 10s...`);
        
        setTimeout(async () => {
            try {
                await supabase.storage.from(BUCKET_WORK).remove([workFile]);
                await supabase.storage.from(BUCKET_READY).remove([readyFile]);
                pendingRequests.delete(request_id);
                console.log(`LOG: Cleanup successful for ${request_id}.`);
            } catch (err) {
                console.error(`LOG: Cleanup error for ${request_id}:`, err.message);
            }
        }, 10000);
    }
    res.sendStatus(200);
});

//sends the processed csv to the xml service with retry logic
async function messengerDispatch(csvContent, enrichedName, workName, retry = 0) {
    const requestId = `REQ_${Date.now()}`;
    const form = new FormData();
    form.append('file', Buffer.from(csvContent), { filename: enrichedName, contentType: 'text/csv' });
    form.append('request_id', requestId);
    form.append('webhook_url', 'http://data_processor:3000/callback');

    try {
        await axios.post(XML_SERVICE_URL, form, { 
            headers: { 
                ...form.getHeaders(), 
                'Authorization': `Bearer ${AUTH_TOKEN}` 
            },
            timeout: 15000 
        });
        pendingRequests.set(requestId, { workFile: workName, readyFile: enrichedName });
        console.log(`LOG: Dispatched to XML Service | ID: ${requestId}`);
    } catch (error) {
        console.error(`LOG: Messenger dispatch error. Retry count: ${retry}/3`);
        if (retry < 3) {
            setTimeout(() => messengerDispatch(csvContent, enrichedName, workName, retry + 1), 5000);
        }
    }
}

//main processor loop that checks for new csv files
async function runProcessor() {
    const { data: files } = await supabase.storage.from(BUCKET_INPUT).list();//list files in input bucket
    const target = files?.find(f => f.name.endsWith('.csv'));
    if (!target) return;

    const originalName = target.name;
    const workName = `processing_${originalName}`;

    try {
        console.log(`\n--- NEW CYCLE: ${originalName} ---`);
        
        const { data: fileBlob } = await supabase.storage.from(BUCKET_INPUT).download(originalName);
        await supabase.storage.from(BUCKET_WORK).upload(workName, fileBlob, { contentType: 'text/csv' });
        await supabase.storage.from(BUCKET_INPUT).remove([originalName]);

        let usdRate = 1.08;
        try {
            const apiRes = await axios.get(`https://v6.exchangerate-api.com/v6/${EXCHANGE_API_KEY}/latest/EUR`);
            usdRate = apiRes.data.conversion_rates.USD || 1.08;
            console.log(`LOG: Live rate obtained: ${usdRate}`);
        } catch (e) {
            console.warn("LOG: Currency API failed, using fallback 1.08");
        }

        const enrichedList = [];
        const csvText = await fileBlob.text();
        const stream = Readable.from(csvText).pipe(csv());

        for await (const row of stream) {
            const appId = getValue(row, ['AppID', 'app_id', 'InternalAppID']) || "0";
            const title = getValue(row, ['Game_Title', 'title', 'Name']) || "Unknown Game";
            const genre = getValue(row, ['Genre', 'genre', 'Category']) || "Action";
            
            const rawDate = getValue(row, ['Release_Date', 'ReleaseDate', 'release_year']) || "2024";
            const yearMatch = rawDate.toString().match(/\d{4}/);
            const year = yearMatch ? yearMatch[0] : "2024";

            const priceEur = getValue(row, ['Price_EUR', 'price', 'Price']) || "0";
            const priceUSD = (parseFloat(priceEur) * usdRate).toFixed(2);

            const score = getValue(row, ['Metacritic_Score', 'ReviewCount', 'reviews']) || "0";

            enrichedList.push({
                InternalAppID: appId,
                Title: title,
                Genre: genre,
                ReleaseYear: year,
                PriceUSD: priceUSD,
                ReviewCount: score
            });
        }

        const csvString = jsonToCSV(enrichedList);
        const enrichedName = `ready_${originalName}`;
        
        await supabase.storage.from(BUCKET_READY).upload(enrichedName, csvString, { contentType: 'text/csv' });
        await messengerDispatch(csvString, enrichedName, workName);
        
    } catch (err) { 
        console.error("LOG: Critical processor error:", err.message); 
    }
}

setInterval(runProcessor, 30000);

const PORT = 3000;
app.listen(PORT, () => console.log(`LOG: Data Processor active on port ${PORT}. Status: Secured.`));