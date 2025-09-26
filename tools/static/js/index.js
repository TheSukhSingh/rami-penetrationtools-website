import { API } from './api.js';
import { connectRunSSE } from './sse.js';
import { WorkflowEditor } from './editor.state.js';
import { attachView } from './editor.view.js';
import { attachDnD } from './editor.dnd.js';
import { attachValidate } from './editor.validate.js';
import { attachPresets } from './editor.presets.js';
import { attachHistory } from "./editor.history.js";

const editor = new WorkflowEditor({ API, connectRunSSE });
attachView(editor);
attachDnD(editor);
attachValidate(editor);
attachPresets(editor);
attachHistory(editor);

window.workflowEditor = editor; 
editor.init();
