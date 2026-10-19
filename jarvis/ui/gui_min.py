"""GUI mínima (tkinter, stdlib) — fallback quando o HUB Qt não está disponível.

Toda lógica permanece no Core/Engine; esta janela só envia texto e exibe
respostas. Não contém regra de negócio. Preferir `python main.py --hub`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from jarvis.core.app import JarvisApp


def run_gui(app: "JarvisApp") -> int:
    import threading
    import tkinter as tk
    from tkinter import scrolledtext

    root = tk.Tk()
    root.title("J.A.R.V.I.S. — console")
    root.geometry("640x440")
    root.configure(bg="#0b1220")

    state_var = tk.StringVar(value=f"estado: {app.states.state}")

    def refresh_state(*_a):
        try:
            state_var.set(f"estado: {app.states.state}")
        except Exception:
            pass

    app.states.add_listener(lambda o, n: root.after(0, refresh_state))

    top = tk.Frame(root, bg="#0b1220")
    top.pack(fill=tk.X, padx=10, pady=8)
    tk.Label(top, text="J.A.R.V.I.S.", fg="#38bdf8", bg="#0b1220",
             font=("Segoe UI", 16, "bold")).pack(side=tk.LEFT)
    tk.Label(top, textvariable=state_var, fg="#94a3b8", bg="#0b1220",
             font=("Segoe UI", 9)).pack(side=tk.RIGHT)

    log_box = scrolledtext.ScrolledText(root, height=18, bg="#0f172a",
                                        fg="#e2e8f0", insertbackground="#e2e8f0",
                                        font=("Consolas", 10))
    log_box.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)
    log_box.insert(tk.END, "Sistemas online. Digite um comando abaixo.\n")
    log_box.configure(state=tk.DISABLED)

    entry = tk.Entry(root, bg="#1e293b", fg="#f1f5f9", insertbackground="#f1f5f9",
                     font=("Segoe UI", 11))
    entry.pack(fill=tk.X, padx=10, pady=6)

    def append(text: str):
        log_box.configure(state=tk.NORMAL)
        log_box.insert(tk.END, text + "\n")
        log_box.see(tk.END)
        log_box.configure(state=tk.DISABLED)

    def send(_event=None):
        text = entry.get().strip()
        if not text:
            return
        entry.delete(0, tk.END)
        append(f"você> {text}")

        def worker():
            result = app.handle_text(text)
            root.after(0, lambda: append(f"jarvis> {result.message}"))
            if result.needs_confirmation:
                root.after(0, lambda: append("        (responda 'sim' ou 'não')"))
            if app.exit_requested:
                root.after(0, root.destroy)

        threading.Thread(target=worker, daemon=True).start()

    entry.bind("<Return>", send)
    tk.Button(root, text="Enviar", command=send, bg="#0369a1", fg="white",
              activebackground="#0284c7", font=("Segoe UI", 10, "bold")).pack(pady=(0, 10))

    def on_close():
        app.request_exit()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    entry.focus()
    root.mainloop()
    return 0
