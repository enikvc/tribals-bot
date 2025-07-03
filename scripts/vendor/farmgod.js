// Placeholder for farmgod script.
// The original script cannot be loaded due to Content Security Policy restrictions.
// This stub provides minimal functionality so that auto_farmer.js can operate.

window.farmgod = {
    init: () => {
        console.log('[farmgod] placeholder init');
    }
};

// Add a dummy Plan farms button if not present
if (!document.querySelector('input.btn.optionButton[value="Plan farms"]')) {
    const btn = document.createElement('input');
    btn.type = 'button';
    btn.className = 'btn optionButton';
    btn.value = 'Plan farms';
    document.body.appendChild(btn);
}

// Add a dummy modal with farm icons if not present
if (!document.querySelector('div.farmGodContent')) {
    const modal = document.createElement('div');
    modal.className = 'farmGodContent';
    for (let i = 0; i < 5; i++) {
        const a = document.createElement('a');
        a.href = '#';
        a.className = 'farmGod_icon farm_icon farm_icon_a';
        a.textContent = `F${i+1}`;
        modal.appendChild(a);
    }
    document.body.appendChild(modal);
}
