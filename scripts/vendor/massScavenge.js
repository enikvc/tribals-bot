// Placeholder for massScavenge script.
// Defines minimal functions used by auto_scavenger.js.

function readyToSend() {
    console.log('[massScavenge] readyToSend called');
    // This placeholder simply logs; real logic should select scavenging units.
}

function sendGroup(index, flag) {
    console.log(`[massScavenge] sendGroup(${index}, ${flag}) called`);
    // Placeholder: perform no action.
}

// Add dummy buttons expected by auto_scavenger if not present
if (!document.querySelector('input.btnSophie[onclick="readyToSend()"]')) {
    const btn1 = document.createElement('input');
    btn1.type = 'button';
    btn1.className = 'btnSophie';
    btn1.setAttribute('onclick', 'readyToSend()');
    btn1.value = 'Ready';
    document.body.appendChild(btn1);
}

if (!document.querySelector('input.btnSophie[onclick="sendGroup(0,false)"]')) {
    const btn2 = document.createElement('input');
    btn2.type = 'button';
    btn2.className = 'btnSophie';
    btn2.setAttribute('onclick', 'sendGroup(0,false)');
    btn2.value = 'Send';
    document.body.appendChild(btn2);
}
