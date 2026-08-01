def _isolate_scroll(scrollable_frame):
    """Impedisce al mousewheel di propagarsi al parent quando il cursore
    è dentro il CTkScrollableFrame — fix per Windows/CustomTkinter."""
    sf = scrollable_frame
    # il canvas interno di CTkScrollableFrame è l'unico widget che riceve scroll
    canvas = sf._parent_canvas if hasattr(sf, "_parent_canvas") else None

    def _block(event):
        # scrolla solo il frame interno, blocca la propagazione
        if canvas:
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        return "break"

    def _bind_wheel(event=None):
        sf.bind_all("<MouseWheel>", _block)

    def _unbind_wheel(event=None):
        sf.unbind_all("<MouseWheel>")

    sf.bind("<Enter>", _bind_wheel)
    sf.bind("<Leave>", _unbind_wheel)
