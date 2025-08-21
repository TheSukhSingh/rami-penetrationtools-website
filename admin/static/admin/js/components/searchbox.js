// admin/static/admin/js/components/searchbox.js

export function makeSearchBox({
  placeholder = "Search…",
  value = "",
  delay = 300,
  onInput = () => {},
} = {}) {
  const root = document.createElement("div");
  root.className = "searchbox";

  const input = document.createElement("input");
  input.type = "search";
  input.className = "searchbox-input";
  input.placeholder = placeholder;
  input.value = value;

  const clearBtn = document.createElement("button");
  clearBtn.type = "button";
  clearBtn.className = "searchbox-clear";
  clearBtn.title = "Clear";
  clearBtn.textContent = "×";

  root.append(input, clearBtn);

  // debounce
  let t = null;
  function handle() {
    if (t) clearTimeout(t);
    t = setTimeout(() => onInput(input.value || ""), delay);
  }

  input.addEventListener("input", handle);
  clearBtn.addEventListener("click", () => {
    if (!input.value) return;
    input.value = "";
    onInput("");
    input.focus();
  });

  injectOnce(
    "searchbox-styles",
    `
    .searchbox{display:flex;align-items:center;gap:8px}
    .searchbox-input{flex:1;min-width:240px;padding:8px 10px;border:1px solid var(--line,#333);border-radius:8px;background:transparent;color:inherit}
    .searchbox-clear{all:unset;cursor:pointer;font-size:18px;line-height:1;padding:4px 8px;opacity:.7}
    .searchbox-clear:hover{opacity:1}
  `
  );

  function setValue(v) {
    input.value = v ?? "";
  }
  function focus() {
    input.focus();
  }

  return { el: root, input, setValue, focus };
}

function injectOnce(id, css) {
  if (document.getElementById(id)) return;
  const style = document.createElement("style");
  style.id = id;
  style.textContent = css;
  document.head.appendChild(style);
}
