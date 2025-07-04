#!/bin/sh
set -e

scripts='https://cdn.jsdelivr.net/gh/enikvc/tribals_it_scripts@refs/tags/1.2/farmgod.js vendor/farmgod.js
https://shinko-to-kuma.com/scripts/massScavenge.js vendor/massScavenge.js'

while read -r url dest; do
  [ -z "$url" ] && continue
  echo "Downloading $url -> $dest"
  mkdir -p "$(dirname "$dest")"
  curl -fsSL "$url" -o "$dest"
done <<EOF2
$scripts
EOF2

echo "All scripts downloaded"
