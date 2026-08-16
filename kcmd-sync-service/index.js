const express = require('express');
const { Storage } = require('@google-cloud/storage');
const kcmd = require('kcmd');
const path = require('path');
const fs = require('fs');

const app = express();
app.use(express.json());

const storage = new Storage();
const BUCKET_NAME = process.env.BUCKET_NAME;
if (!BUCKET_NAME) {
  console.error('ERROR: BUCKET_NAME environment variable is required');
  process.exit(1);
}
const WORKSPACE_DIR = '/tmp/workspace';

// Helper to get access token from metadata server
async function getAccessToken() {
  try {
    const res = await fetch('http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token', {
      headers: { 'Metadata-Flavor': 'Google' }
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    return data.access_token;
  } catch (err) {
    console.error('Failed to get metadata token, falling back to ambient:', err);
    return null;
  }
}

// Helper to clean directory
async function cleanDirectory(dir) {
  if (fs.existsSync(dir)) {
    await fs.promises.rm(dir, { recursive: true, force: true });
  }
  await fs.promises.mkdir(dir, { recursive: true });
}

// Helper to download GCS bucket to local dir
async function downloadDirectory(bucketName, localFolder) {
  console.log(`Downloading gs://${bucketName} to ${localFolder}...`);
  const [files] = await storage.bucket(bucketName).getFiles();
  for (const file of files) {
    const localPath = path.join(localFolder, file.name);
    await fs.promises.mkdir(path.dirname(localPath), { recursive: true });
    await file.download({ destination: localPath });
    console.log(`Downloaded ${file.name}`);
  }
}

// Helper to upload local dir to GCS bucket
async function uploadDirectory(bucketName, localFolder) {
  console.log(`Uploading ${localFolder} to gs://${bucketName}...`);
  const walk = async (dir) => {
    const entries = await fs.promises.readdir(dir, { withFileTypes: true });
    for (const entry of entries) {
      const res = path.resolve(dir, entry.name);
      if (entry.isDirectory()) {
        await walk(res);
      } else {
        const relativePath = path.relative(localFolder, res);
        // Skip temporary or lock files if any
        if (entry.name.startsWith('.') || entry.name === 'package-lock.json') {
             continue;
        }
        await storage.bucket(bucketName).upload(res, {
          destination: relativePath,
        });
        console.log(`Uploaded ${relativePath}`);
      }
    }
  };
  await walk(localFolder);
}

// Set up KCMD ApiContext
async function setupKcmdContext() {
  const token = await getAccessToken();
  const project = process.env.GOOGLE_CLOUD_PROJECT;
  const location = process.env.GOOGLE_CLOUD_LOCATION || 'us-central1';

  if (!project) {
    throw new Error("GOOGLE_CLOUD_PROJECT environment variable is required");
  }

  if (token) {
    process.env['KCMD_ACCESS_TOKEN'] = token;
    console.log("Using token from metadata server.");
  } else {
    console.log("No metadata token found, relying on ambient gcloud auth (if any).");
  }
  process.env['GOOGLE_CLOUD_PROJECT'] = project;
  process.env['GOOGLE_CLOUD_LOCATION'] = location;

  return kcmd.gcp.ApiContext.default();
}

app.post('/', async (req, res) => {
  console.log('Received request:', JSON.stringify(req.body));
  console.log('Headers:', JSON.stringify(req.headers));

  // Determine action
  let action = req.body.action;

  // Check if Pub/Sub trigger (envelope)
  if (req.body.message) {
    console.log('Detected Pub/Sub message.');
    // Default action for BQ update is pull
    action = 'pull';
    try {
      const data = Buffer.from(req.body.message.data, 'base64').toString();
      console.log('Pub/Sub data:', data);
      const parsedData = JSON.parse(data);
      if (parsedData.action) {
          action = parsedData.action;
      }
    } catch (e) {
      console.log('Failed to parse Pub/Sub data, defaulting to action: pull');
    }
  }
  
  // Check if GCS event (Eventarc)
  const ceType = req.headers['ce-type'];
  if (ceType === 'google.cloud.storage.object.v1.finalized') {
    console.log('Detected GCS finalize event.');
    // Check if the change was made by our own service account to avoid loops
    // Eventarc payload might have resourceState or similar, but the easiest is to check
    // if we want to run push. GCS update always triggers push.
    action = 'push';
    
    // Optional: filter out changes to non-metadata files
    const objectName = req.body.name;
    if (objectName && !objectName.startsWith('bundle/') && objectName !== 'catalog.yaml') {
        console.log(`Ignoring GCS event for non-metadata file: ${objectName}`);
        return res.status(200).send('Ignored');
    }
  }

  if (!action) {
    return res.status(400).send('Missing action (pull or push)');
  }

  console.log(`Executing action: ${action}`);

  try {
    const ctx = await setupKcmdContext();
    await cleanDirectory(WORKSPACE_DIR);
    
    // Download current state from GCS
    try {
        await downloadDirectory(BUCKET_NAME, WORKSPACE_DIR);
    } catch (err) {
        console.log("Failed to download from GCS (bucket might be empty). Proceeding...", err.message);
    }

    const snapshot = await kcmd.CatalogSnapshot.fromPath(WORKSPACE_DIR, ctx);
    const sync = new kcmd.CatalogSync(new kcmd.dataplex.CatalogClient(ctx), snapshot);

    if (action === 'pull') {
      console.log('Running pull...');
      const pullResult = await sync.pull();
      if (!pullResult.success) {
        throw new Error(`Pull failed: ${pullResult.details}`);
      }
      console.log('Pull successful. Finalizing...');
      await snapshot.finalize();
      
      // Upload updated files to GCS
      await uploadDirectory(BUCKET_NAME, WORKSPACE_DIR);
      res.status(200).send('Pull and GCS upload successful');
      
    } else if (action === 'push') {
      console.log('Running push...');
      const pushResult = await sync.push();
      if (!pushResult.success) {
        throw new Error(`Push failed: ${pushResult.details}`);
      }
      res.status(200).send('Push to Knowledge Catalog successful');
    } else {
      res.status(400).send(`Unknown action: ${action}`);
    }

  } catch (err) {
    console.error('Error during execution:', err);
    res.status(500).send(`Error: ${err.message}`);
  }
});

const PORT = process.env.PORT || 8080;
app.listen(PORT, () => {
  console.log(`Server listening on port ${PORT}`);
});
