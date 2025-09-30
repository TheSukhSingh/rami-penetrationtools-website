import { API } from './api.js';
import { connectRunSSE } from './sse.js';
import { WorkflowEditor } from './editor.state.js';
import { attachView } from './editor.view.js';
import { attachDnD } from './editor.dnd.js';
import { attachValidate } from './editor.validate.js';
import { attachPresets } from './editor.presets.js';
import { attachHistory } from "./editor.history.js";
// index.js (or editor.view.js if that’s where you wire the Run button)
import { getSpecs, computeStageViolations } from './editor.validate.js';

async function preRunValidate(editor) {
  // 1) General structure + IO compat
  const warnings = editor.validateWorkflow() || [];

  // 2) Stage ordering (server is authoritative, but warn early)
  editor._specs = editor._specs || await getSpecs();
  const stageMap = editor._specs?.tool_stage_map || {};
  const stageErrs = computeStageViolations(editor.nodes || [], editor.connections || [], stageMap);

  // show banner if needed (validateWorkflow already paints it; append stage errs)
  if (stageErrs.length) {
    const banner = document.getElementById("warningBanner");
    const text = document.getElementById("warningText");
    if (banner && text) {
      banner.classList.remove("hidden");
      const prev = text.innerHTML ? text.innerHTML + "<br>" : "";
      text.innerHTML = prev + stageErrs.map(s => s.replace(/&/g,"&amp;")
                         .replace(/</g,"&lt;").replace(/>/g,"&gt;")).join("<br>");
    }
  }
  return { warnings, stageErrs };
}

// hook once on init
(async () => {
  const runBtn = document.getElementById('runBtn');
  if (runBtn) {
    runBtn.addEventListener('click', async (e) => {
      const { warnings, stageErrs } = await preRunValidate(editor);

      // Optional: block hard failures (no-compatible-bucket, stage violation)
      const hardError =
        (warnings || []).some(w => w.includes('no compatible buckets') ||
                                   w.includes('single chain') ||
                                   w.includes('exactly one start') ||
                                   w.includes('exactly one end')) ||
        (stageErrs || []).length > 0;

      if (hardError) {
        // stop here; user can fix per banner
        return;
      }
      // otherwise proceed with your existing start flow
      editor.startRun?.();
    });
  }
})();

const editor = new WorkflowEditor({ API, connectRunSSE });
attachView(editor);
attachDnD(editor);
attachValidate(editor);
attachPresets(editor);
attachHistory(editor);

window.workflowEditor = editor; 
editor.init();
