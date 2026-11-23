/* Diálogos propios de FixIT: reemplazan prompt()/alert() del navegador.
 *   askReason({ title, message, placeholder, confirmText }) -> Promise<string|null>
 *   notify(mensaje, tipo)  tipo: 'info' | 'error' | 'success'
 */
(function () {
  function el(tag, cls, text) {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text) n.textContent = text;
    return n;
  }

  window.askReason = function (opts) {
    const o = Object.assign({ title: 'Motivo', message: '', placeholder: 'Describe el motivo...', confirmText: 'Confirmar' }, opts || {});
    return new Promise(function (resolve) {
      const dlg = el('dialog', 'rounded-lg shadow-2xl p-0 w-full max-w-md backdrop:bg-slate-900/50 backdrop:backdrop-blur-sm');
      const form = el('form', 'p-6 space-y-4');
      form.method = 'dialog';
      form.noValidate = true;  // el mensaje de validación propio, en español
      form.appendChild(el('h2', 'text-lg font-bold text-slate-900', o.title));
      if (o.message) form.appendChild(el('p', 'text-sm text-slate-600', o.message));
      const area = el('textarea', 'w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 min-h-[96px]');
      area.placeholder = o.placeholder;
      area.required = true;
      area.maxLength = 500;
      const error = el('p', 'hidden text-xs font-semibold text-rose-600', 'El motivo es obligatorio.');
      const actions = el('div', 'flex justify-end gap-2 pt-2');
      const cancel = el('button', 'px-4 py-2 rounded-lg border border-slate-300 text-sm font-semibold text-slate-700 hover:bg-slate-50', 'Cancelar');
      cancel.type = 'button';
      const ok = el('button', 'px-4 py-2 rounded-lg bg-rose-600 hover:bg-rose-700 text-white text-sm font-bold', o.confirmText);
      ok.type = 'submit';
      actions.append(cancel, ok);
      form.append(area, error, actions);
      dlg.appendChild(form);
      document.body.appendChild(dlg);

      let result = null;
      cancel.addEventListener('click', function () { dlg.close(); });
      form.addEventListener('submit', function (ev) {
        const value = area.value.trim();
        if (!value) { ev.preventDefault(); error.classList.remove('hidden'); area.focus(); return; }
        result = value;
      });
      dlg.addEventListener('close', function () { dlg.remove(); resolve(result); });
      dlg.showModal();
      area.focus();
    });
  };

  window.notify = function (message, type) {
    const colors = { error: 'bg-rose-600', success: 'bg-emerald-600', info: 'bg-slate-900' };
    let box = document.getElementById('fixit-toasts');
    if (!box) {
      box = el('div', 'fixed top-4 right-4 z-[60] flex flex-col gap-2 no-print');
      box.id = 'fixit-toasts';
      box.setAttribute('role', 'status');
      box.setAttribute('aria-live', 'polite');
      document.body.appendChild(box);
    }
    const t = el('div', 'text-white text-sm font-semibold px-4 py-3 rounded-lg shadow-lg max-w-xs ' + (colors[type] || colors.info), message);
    box.appendChild(t);
    setTimeout(function () { t.remove(); }, 3500);
  };
})();
