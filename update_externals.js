const https = require('https');
const fs = require('fs');
const path = require('path');

const scripts = [
  { url: 'https://cdn.jsdelivr.net/gh/enikvc/tribals_it_scripts@refs/tags/1.2/farmgod.js', file: 'vendor/farmgod.js' },
  { url: 'https://shinko-to-kuma.com/scripts/massScavenge.js', file: 'vendor/massScavenge.js' }
];

function download(url, dest) {
  return new Promise((resolve, reject) => {
    https.get(url, (res) => {
      if (res.statusCode !== 200) {
        reject(new Error(`Request failed with status ${res.statusCode}`));
        res.resume();
        return;
      }
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        fs.mkdirSync(path.dirname(dest), { recursive: true });
        fs.writeFileSync(dest, data);
        resolve();
      });
    }).on('error', reject);
  });
}

(async () => {
  try {
    for (const s of scripts) {
      console.log(`Downloading ${s.url} -> ${s.file}`);
      await download(s.url, path.join(__dirname, s.file));
    }
    console.log('All scripts downloaded');
  } catch (err) {
    console.error('Failed to download external scripts:', err);
    process.exit(1);
  }
})();
