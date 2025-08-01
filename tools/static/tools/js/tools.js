// Global state
let currentTool = "subfinder";
let terminalHistory = [];

// Initialize the application
document.addEventListener("DOMContentLoaded", function () {
  initializeApp();
});

function initializeApp() {
  setupEventListeners();
  initializeParticles();
  // showToolForm(currentTool);
  resetForm();
}

function setupEventListeners() {
  // Tool selection
  const toolItems = document.querySelectorAll(".tool-item");
  toolItems.forEach((item) => {
    item.addEventListener("click", function () {
      const toolName = this.dataset.tool;
      selectTool(toolName);
    });
  });

  // Input method radio buttons
  setupInputMethodListeners();

  // File input handlers
  setupFileInputHandlers();
}

function setupInputMethodListeners() {
  const forms = document.querySelectorAll(".tool-form");
  forms.forEach((form) => {
    const inputMethodRadios = form.querySelectorAll(
      'input[name$="-input-method"]'
    );
    inputMethodRadios.forEach((radio) => {
      radio.addEventListener("change", function () {
        const toolName = this.name.split("-")[0];
        const method = this.value;
        toggleInputMethod(toolName, method);
      });
    });
  });
}

// function setupFileInputHandlers() {
//   const fileInputs = document.querySelectorAll(".file-input");
//   fileInputs.forEach((input) => {
//     input.addEventListener("change", function () {
//       const display = this.nextElementSibling;
//       const span = display.querySelector("span");

//       if (this.files.length > 0) {
//         span.textContent = this.files[0].name;
//         display.style.borderColor = "var(--cyber-cyan)";
//         display.style.boxShadow = "0 0 12px rgba(0, 255, 224, 0.35)";
//       } else {
//         span.textContent = "Choose file or drag here";
//         display.style.borderColor = "var(--glass-border)";
//         display.style.boxShadow = "none";
//       }
//     });
//   });
// }

function setupFileInputHandlers() {
  document.querySelectorAll(".file-input-wrapper").forEach((wrapper) => {
    const input = wrapper.querySelector(".file-input");
    const display = wrapper.querySelector(".file-input-display span");

    // --- existing change handler ---
    input.addEventListener("change", () => {
      if (input.files.length) {
        display.textContent = input.files[0].name;
        wrapper.classList.add("dragover");
      } else {
        display.textContent = "Choose file or drag here";
        wrapper.classList.remove("dragover");
      }
    });

    // --- drag & drop support ---
    ["dragenter", "dragover"].forEach((evt) =>
      wrapper.addEventListener(evt, (e) => {
        e.preventDefault();
        wrapper.classList.add("dragover");
      })
    );
    ["dragleave", "drop"].forEach((evt) =>
      wrapper.addEventListener(evt, (e) => {
        e.preventDefault();
        wrapper.classList.remove("dragover");
        if (evt === "drop" && e.dataTransfer.files.length) {
          input.files = e.dataTransfer.files;
          input.dispatchEvent(new Event("change"));
        }
      })
    );
  });
}

function initializeParticles() {
  const particlesContainer = document.getElementById("particles");

  for (let i = 0; i < 15; i++) {
    const particle = document.createElement("div");
    particle.className = "particle";
    particle.style.left = `${Math.random() * 100}%`;
    particle.style.top = `${Math.random() * 100}%`;
    particle.style.animationDelay = `${Math.random() * 3}s`;
    particle.style.animationDuration = `${2 + Math.random() * 2}s`;
    particlesContainer.appendChild(particle);
  }
}

function showPrompt() {
  const terminalOutput = document.getElementById("terminalOutput");
  const promptEl = document.createElement("div");
  promptEl.className = "terminal-line prompt-line";
  promptEl.innerHTML = `<span class="terminal-prompt">hackr@gg > </span>`;
  terminalOutput.appendChild(promptEl);
  terminalOutput.scrollTop = terminalOutput.scrollHeight;
}

// Clears everything *and* shows one prompt
function clearTerminal() {
  const terminalOutput = document.getElementById("terminalOutput");
  terminalOutput.innerHTML = "";
  showPrompt();
}

// Appends a line of text *above* the current prompt, then re-draws the prompt
function appendToTerminal(text, isCommand = false) {
  const terminalOutput = document.getElementById("terminalOutput");

  // Remove the existing trailing prompt
  const last = terminalOutput.lastElementChild;
  if (last && last.classList.contains("prompt-line")) {
    terminalOutput.removeChild(last);
  }

  const lineEl = document.createElement("div");
  lineEl.className = "terminal-line";

  if (isCommand) {
    // flatten any newlines in the command
    const flat = text.replace(/(\r?\n)+/g, " ").trim();
    lineEl.innerHTML =
      `<span class="terminal-prompt">hackr@gg > </span>` +
      `<span class="terminal-text">${flat}</span>`;
  } else {
    lineEl.innerHTML = `<span class="terminal-text">${text}</span>`;
  }

  terminalOutput.appendChild(lineEl);

  // Re-add the prompt at the bottom
  if (!isCommand) {
    showPrompt();
  }
  terminalOutput.scrollTop = terminalOutput.scrollHeight;
}

function selectTool(toolName) {
  // Update active tool item
  document.querySelectorAll(".tool-item").forEach((item) => {
    item.classList.remove("active");
  });
  document.querySelector(`[data-tool="${toolName}"]`).classList.add("active");

  // Update current tool
  currentTool = toolName;

  // Update config title
  const toolNames = {
    subfinder: "Subfinder Configuration",
    dnsx: "Dnsx Configuration",
    naabu: "Naabu Configuration",
    katana: "Katana Configuration",
    gau: "Gau Configuration",
    httpx: "Httpx Configuration",
    gospider: "GoSpider Configuration",
    hakrawler: "Hakrawler Configuration",
    linkfinder: "Linkfinder Configuration",
    "github-subdomains": "Github-subdomains Configuration",
  };

  document.getElementById("configTitle").textContent = toolNames[toolName];

  // Show corresponding form
  showToolForm(toolName);
}

function showToolForm(toolName) {
  // Hide all forms
  document.querySelectorAll(".tool-form").forEach((form) => {
    form.classList.remove("active");
  });

  // Show selected form
  const targetForm = document.getElementById(`${toolName}-form`);
  if (targetForm) {
    targetForm.classList.add("active");
  }
}

function toggleInputMethod(toolName, method) {
  const manualInput = document.getElementById(`${toolName}-manual-input`);
  const fileInput = document.getElementById(`${toolName}-file-input`);

  if (method === "manual") {
    manualInput.classList.remove("hidden");
    fileInput.classList.add("hidden");
  } else {
    manualInput.classList.add("hidden");
    fileInput.classList.remove("hidden");
  }
}

function executeScan() {
  const activeForm = document.querySelector(".tool-form.active");
  if (!activeForm) return;

  // const formData = collectFormData(activeForm);
  // const command = generateCommand(currentTool, formData);

  // build a FormData payload
  const formData = new FormData();
  // tell the backend which tool
  formData.append("tool", currentTool);
  // collect all fields, including files
  activeForm.querySelectorAll("input, textarea, select").forEach((input) => {
    if (input.type === "file") {
      if (input.files.length > 0) {
        formData.append(input.name, input.files[0]);
      }
    } else if (
      (input.type === "radio" || input.type === "checkbox") &&
      !input.checked
    ) {
      return; // skip unchecked
    } else {
      formData.append(input.name, input.value);
    }
  });
  // for your terminal UI, still generate the CLI preview
  // build preview-friendly options
  const previewOptions = {};
  for (let [key, value] of formData.entries()) {
  // if it’s a File, swap in just the name
  if (value instanceof File) value = value.name;

  // if we’ve never seen this key, just set it
  if (!(key in previewOptions)) {
    previewOptions[key] = value;
  } else {
    // if it was a scalar, turn it into a 2-item array
    if (!Array.isArray(previewOptions[key])) {
      previewOptions[key] = [previewOptions[key]];
    }
    // now push the new one
    previewOptions[key].push(value);
  }
}
  const command = generateCommand(currentTool, previewOptions);

  clearTerminal();
  appendToTerminal(command, true);

  const scanBtn = document.querySelector(".scan-btn");
  const orig = scanBtn.innerHTML;
  scanBtn.innerHTML = `
    <div class="loading-spinner"></div>
    <span>Scanning…<span>
  `;
  scanBtn.disabled = true;

  fetch("/tools/api/scan", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tool: currentTool, options: formData }),
  })
  fetch("/tools/api/scan", {
    method: "POST",
    body: formData,
  })
    .then((res) => res.json())
    .then((data) => {
      if (data.status === "error") {
        appendToTerminal(`Error: ${data.message}`);
      } else {
        data.output.split("\n").forEach((line) => appendToTerminal(line));
      }
    })
    .catch((err) => {
      appendToTerminal(`Fetch error: ${err.message}`);
    })
    .finally(() => {
      scanBtn.innerHTML = orig;
      scanBtn.disabled = false;
    });
  // fetch("/tools/api/scan", {
  //   method: "POST",
  //   body: formData,
  // })
  //   .then((resp) =>
  //     resp.text().then((text) => {
  //       if (!resp.ok) {
  //         // HTTP 4xx/5xx → show raw HTML or error message
  //         throw new Error(text);
  //       }
  //       // try to parse JSON; if it fails, return raw text
  //       try {
  //         return JSON.parse(text);
  //       } catch {
  //         return { output: text };
  //       }
  //     })
  //   )
  //   .then((result) => {
  //     // result is either your JSON {status,output,…} or {output:rawText}
  //     appendToTerminal(result.output || JSON.stringify(result));
  //     // re-render prompt…
  //   })
  //   .catch((err) => {
  //     appendToTerminal(`Error: ${err.message}`);
  //   })
  //   .finally(() => {
  //     scanBtn.innerHTML = orig;
  //     scanBtn.disabled = false;
  //   });
}

function collectFormData(form) {
  const data = {};

  // Get all form inputs
  const inputs = form.querySelectorAll("input, textarea, select");

  inputs.forEach((input) => {
    if (input.type === "radio") {
      if (input.checked) {
        data[input.name] = input.value;
      }
    } else if (input.type === "checkbox") {
      if (!data[input.name]) {
        data[input.name] = [];
      }
      if (input.checked) {
        data[input.name].push(input.value);
      }
    } else if (input.type === "file") {
      if (input.files.length > 0) {
        data[input.name] = input.files[0].name;
      }
    } else {
      data[input.name] = input.value;
    }
  });

  return data;
}

/**
 * Builds the full CLI command string for each reconnaissance tool.
 * Assumes `formData` contains keys matching your input `name` attributes:
 *   "<tool>-input-method", "<tool>-manual", "<tool>-file",
 *   plus all the option names shown below.
 */
function generateCommand(toolName, formData) {
  let cmd = toolName;

  switch (toolName) {
    case "subfinder":
      // Targets
      if (formData["subfinder-input-method"] === "manual") {
        (formData["subfinder-manual"] || "")
          .split("\n")
          .map((s) => s.trim())
          .filter(Boolean)
          .forEach((d) => (cmd += ` -d ${d}`));
      } else if (formData["subfinder-file"]) {
        cmd += ` -f ${formData["subfinder-file"]}`;
      }
      // Options
      if (formData["subfinder-silent"] === "yes") cmd += " -silent";
      if (formData["subfinder-threads"])
        cmd += ` -t ${formData["subfinder-threads"]}`;
      if (formData["subfinder-timeout"])
        cmd += ` -timeout ${formData["subfinder-timeout"]}`;
      if (formData["subfinder-all"] === "yes") cmd += " -all";
      if (formData["subfinder-max-time"])
        cmd += ` -max-time ${formData["subfinder-max-time"]}`;
      break;

    case "dnsx":
      // Targets
      if (formData["dnsx-input-method"] === "manual") {
        (formData["dnsx-manual"] || "")
          .split("\n")
          .map((s) => s.trim())
          .filter(Boolean)
          .forEach((d) => (cmd += ` -d ${d}`));
      } else if (formData["dnsx-file"]) {
        cmd += ` -f ${formData["dnsx-file"]}`;
      }
      // Record types
      if (Array.isArray(formData["dnsx-record-types"])) {
        formData["dnsx-record-types"].forEach(
          (type) => (cmd += ` -${type.toLowerCase()}`)
        );
      }
      // Options
      if (formData["dnsx-silent"] === "yes") cmd += " -silent";
      if (formData["dnsx-threads"]) cmd += ` -t ${formData["dnsx-threads"]}`;
      if (formData["dnsx-retry"]) cmd += ` -retry ${formData["dnsx-retry"]}`;
      break;

    case "naabu":
      // Targets
      if (formData["naabu-input-method"] === "manual") {
        (formData["naabu-manual"] || "")
          .split("\n")
          .map((s) => s.trim())
          .filter(Boolean)
          .forEach((h) => (cmd += ` -host ${h}`));
      } else if (formData["naabu-file"]) {
        cmd += ` -l ${formData["naabu-file"]}`;
      }
      // Options
      if (formData["naabu-silent"] === "yes") cmd += " -silent";
      if (formData["naabu-top-ports"])
        cmd += ` -top-ports ${formData["naabu-top-ports"]}`;
      if (formData["naabu-rate"]) cmd += ` -rate ${formData["naabu-rate"]}`;
      if (formData["naabu-timeout"])
        cmd += ` -timeout ${formData["naabu-timeout"]}`;
      break;

    case "katana":
      // Targets
      if (formData["katana-input-method"] === "manual") {
        (formData["katana-manual"] || "")
          .split("\n")
          .map((s) => s.trim())
          .filter(Boolean)
          .forEach((u) => (cmd += ` -u ${u}`));
      } else if (formData["katana-file"]) {
        cmd += ` -f ${formData["katana-file"]}`;
      }
      // Options
      if (formData["katana-silent"] === "yes") cmd += " -silent";
      if (formData["katana-js"] === "yes") cmd += " -js";
      if (formData["katana-headless"] === "yes") cmd += " -headless";
      if (formData["katana-c"]) cmd += ` -c ${formData["katana-c"]}`;
      if (formData["katana-timeout"])
        cmd += ` -timeout ${formData["katana-timeout"]}`;
      break;

    case "gau":
      // Targets
      if (formData["gau-input-method"] === "manual") {
        (formData["gau-manual"] || "")
          .split("\n")
          .map((s) => s.trim())
          .filter(Boolean)
          .forEach((d) => (cmd += ` -d ${d}`));
      } else if (formData["gau-file"]) {
        cmd += ` -f ${formData["gau-file"]}`;
      }
      // Options
      if (formData["gau-threads"])
        cmd += ` -threads ${formData["gau-threads"]}`;
      if (formData["gau-timeout"])
        cmd += ` -timeout ${formData["gau-timeout"]}`;
      if (formData["gau-subs"] === "yes") cmd += " --subs";
      if (formData["gau-providers"])
        cmd += ` --providers ${formData["gau-providers"]}`;
      if (formData["gau-retries"])
        cmd += ` --retries ${formData["gau-retries"]}`;
      if (formData["gau-blacklist"])
        cmd += ` --blacklist ${formData["gau-blacklist"]}`;
      if (formData["gau-json"] === "yes") cmd += " --json";
      break;

    case "gospider":
      // Targets
      if (formData["gospider-input-method"] === "manual") {
        (formData["gospider-manual"] || "")
          .split("\n")
          .map((s) => s.trim())
          .filter(Boolean)
          .forEach((d) => (cmd += ` -d ${d}`));
      } else if (formData["gospider-file"]) {
        cmd += ` -f ${formData["gospider-file"]}`;
      }
      // Options
      if (formData["gospider-threads"])
        cmd += ` --threads ${formData["gospider-threads"]}`;
      if (formData["gospider-c"]) cmd += ` -c ${formData["gospider-c"]}`;
      if (formData["gospider-d"]) cmd += ` -d ${formData["gospider-d"]}`;
      if (formData["gospider-m"]) cmd += ` -m ${formData["gospider-m"]}`;
      if (formData["gospider-subs"] === "yes") cmd += " --subs";
      if (formData["gospider-u"]) cmd += ` -u "${formData["gospider-u"]}"`;
      if (formData["gospider-p"]) cmd += ` -p ${formData["gospider-p"]}`;
      break;

    case "hakrawler":
      // Targets
      if (formData["hakrawler-input-method"] === "manual") {
        (formData["hakrawler-manual"] || "")
          .split("\n")
          .map((s) => s.trim())
          .filter(Boolean)
          .forEach((d) => (cmd += ` -d ${d}`));
      } else if (formData["hakrawler-file"]) {
        cmd += ` -f ${formData["hakrawler-file"]}`;
      }
      // Options
      if (formData["hakrawler-d"]) cmd += ` -d ${formData["hakrawler-d"]}`;
      if (formData["hakrawler-subs"] === "yes") cmd += " --subs";
      if (formData["hakrawler-threads"])
        cmd += ` --threads ${formData["hakrawler-threads"]}`;
      if (formData["hakrawler-timeout"])
        cmd += ` --timeout ${formData["hakrawler-timeout"]}`;
      if (formData["hakrawler-unique"] === "yes") cmd += " --unique";
      if (formData["hakrawler-json"] === "yes") cmd += " --json";
      break;

    case "linkfinder":
      // Domain (required)
      if (formData["linkfinder-domain"])
        cmd += ` -i ${formData["linkfinder-domain"]}`;
      // Pattern
      if (formData["linkfinder-regex"])
        cmd += ` -r "${formData["linkfinder-regex"]}"`;
      // Options
      if (formData["linkfinder-burp"] === "yes") cmd += " -b";
      if (formData["linkfinder-cookies"])
        cmd += ` -c "${formData["linkfinder-cookies"]}"`;
      if (formData["linkfinder-timeout"])
        cmd += ` -t ${formData["linkfinder-timeout"]}`;
      break;

    case "github-subdomains":
      // URL (required)
      if (formData["github-url"]) cmd += ` -u ${formData["github-url"]}`;
      // Options
      if (formData["github-extended"] === "yes") cmd += " -e";
      if (formData["github-exit-disabled"] === "yes")
        cmd += " --exit-on-disabled";
      if (formData["github-raw"] === "yes") cmd += " -r";
      break;

    default:
      // Unknown tool
      console.warn(`No command builder for tool: ${toolName}`);
      break;
  }

  return cmd;
}

function resetForm() {
  const activeForm = document.querySelector(".tool-form.active");
  if (!activeForm) return;

  // Reset form
  activeForm.reset();

  // Reset file inputs
  const fileInputs = activeForm.querySelectorAll(".file-input");
  fileInputs.forEach((input) => {
    const display = input.nextElementSibling;
    const span = display.querySelector("span");
    span.textContent = "Choose file or drag here";
    display.style.borderColor = "var(--glass-border)";
    display.style.boxShadow = "none";
  });

  // Reset input method visibility
  const toolName = currentTool;
  const manualInput = document.getElementById(`${toolName}-manual-input`);
  const fileInput = document.getElementById(`${toolName}-file-input`);

  if (manualInput && fileInput) {
    manualInput.classList.remove("hidden");
    fileInput.classList.add("hidden");
  }

  // Reset terminal
  const terminalOutput = document.getElementById("terminalOutput");
  terminalOutput.innerHTML = `
        <div class="terminal-line">
            <span class="terminal-prompt">hacker@gg > </span>
            <span class="terminal-text">waiting for scan...</span>
        </div>
    `;

  // Visual feedback
  const resetBtn = document.querySelector(".reset-btn");
  const originalText = resetBtn.innerHTML;

  resetBtn.innerHTML = `
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M9 12l2 2 4-4"></path>
        </svg>
        <span>Reset Complete</span>
    `;

  setTimeout(() => {
    resetBtn.innerHTML = originalText;
  }, 1500);
}

function showPastScans() {
  // Visual feedback only - no functionality as requested
  const historyBtn = document.querySelector(".history-btn");
  const originalText = historyBtn.innerHTML;

  historyBtn.innerHTML = `
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 2v6l3-3"></path>
            <path d="M12 2v6l-3-3"></path>
            <circle cx="12" cy="12" r="10"></circle>
        </svg>
        <span>Loading...</span>
    `;

  setTimeout(() => {
    historyBtn.innerHTML = originalText;

    // Add a terminal message
    const terminalOutput = document.getElementById("terminalOutput");
    const messageLine = document.createElement("div");
    messageLine.className = "terminal-line";
    messageLine.innerHTML = `
            <span class="terminal-prompt">hacker@gg > </span>
            <span class="terminal-text">Past scans feature coming soon...</span>
        `;
    terminalOutput.appendChild(messageLine);
    terminalOutput.scrollTop = terminalOutput.scrollHeight;
  }, 1000);
}

// Add CSS for loading spinner
const style = document.createElement("style");
style.textContent = `
    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
`;
document.head.appendChild(style);
