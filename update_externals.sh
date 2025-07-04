#!/bin/bash
# update_externals.sh
# Shell script to download external scripts

# Create vendor directory if it doesn't exist
mkdir -p vendor

echo "📥 Downloading external scripts..."
echo ""

# Download farmgod.js
echo "⬇️  Downloading farmgod.js..."
if curl -L -o vendor/farmgod.js "https://cdn.jsdelivr.net/gh/enikvc/tribals_it_scripts@refs/tags/1.2/farmgod.js"; then
    echo "✅ Successfully downloaded farmgod.js"
    echo "   Size: $(du -h vendor/farmgod.js | cut -f1)"
else
    echo "❌ Failed to download farmgod.js"
fi
echo ""

# Download massScavenge.js
echo "⬇️  Downloading massScavenge.js..."
if curl -L -o vendor/massScavenge.js "https://shinko-to-kuma.com/scripts/massScavenge.js"; then
    echo "✅ Successfully downloaded massScavenge.js"
    echo "   Size: $(du -h vendor/massScavenge.js | cut -f1)"
else
    echo "❌ Failed to download massScavenge.js"
fi
echo ""

echo "🎉 Download process complete!"