// Popup shown when the toolbar icon is clicked. Its only real job is a
// lightweight "are we logged in" check -- via background.js, same reason
// content.js goes through background.js rather than fetching directly (see
// background.js's top comment: the request needs to originate from the
// extension's own chrome-extension://<id> origin).

const statusDot = document.getElementById("status-dot");
const statusText = document.getElementById("status-text");
const openAppLink = document.getElementById("open-app-link");

async function checkAuthAndRender() {
  try {
    const { loggedIn } = await chrome.runtime.sendMessage({ type: "CHECK_AUTH" });
    if (loggedIn) {
      statusDot.className = "status-dot logged-in";
      statusText.textContent = "Logged in";
    } else {
      statusDot.className = "status-dot logged-out";
      statusText.textContent = "Not logged in";
      openAppLink.href = LOGIN_URL;
      openAppLink.textContent = "Log in →";
    }
  } catch (error) {
    statusDot.className = "status-dot logged-out";
    statusText.textContent = "Couldn't reach the app";
  }
}

checkAuthAndRender();
