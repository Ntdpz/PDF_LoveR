"""Module entrypoint. Divert frozen workers before importing Tk."""
import multiprocessing
import sys


def main():
    multiprocessing.freeze_support()
    import customtkinter as ctk
    from pdf_lover.app import App
    ctk.set_appearance_mode("light")
    window = ctk.CTk()
    if len(sys.argv) == 3 and sys.argv[1] == "--self-test":
        from pdf_lover.diagnostics.self_test import run
        run(window, App, sys.argv[2])
    else:
        App(window)
        window.mainloop()


if __name__ == "__main__":
    main()
