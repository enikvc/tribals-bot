chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg && msg.type === 'fetch-script' && msg.src) {
    fetch(msg.src)
      .then(res => res.text())
      .then(code => sendResponse({code}))
      .catch(err => sendResponse({error: err.toString()}));
    return true; // async response
  }
});
