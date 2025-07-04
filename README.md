# tribals-bot

This project bundles multiple automation scripts originally for Tampermonkey into a single Chrome extension. The extension loads the scripts on their respective pages so you can use them without Tampermonkey.

## Included scripts
- **auto_buyer.js** – automatically buys premium resources on the exchange page.
- **auto_farmer.js** – automates farming actions on the farming screen.
- **auto_scavenger.js** – runs mass scavenging with human-like timing.
- **auto_sniper.js** – placeholder for a sniping script.

The scripts are located in the `scripts/` folder and are referenced from `manifest.json`.

## Getting the external helpers

Some of the automation relies on third‑party scripts. To keep them up to date,
the repository provides two small helpers that download the files into the
`vendor/` directory. You can use either Node.js or a simple shell script before
loading the extension:

```bash
# with Node (requires Node.js 12+)
node update_externals.js

# or using curl/wget if Node isn't available
./update_externals.sh
```

If the files are missing, the extension will not be able to start.

## Installing the extension
1. Open `chrome://extensions/` in your browser.
2. Enable “Developer mode”.
3. Click “Load unpacked” and select this repository directory.

The extension will now inject the scripts on the matching pages.
