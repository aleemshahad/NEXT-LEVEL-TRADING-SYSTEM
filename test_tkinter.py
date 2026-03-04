import tkinter as tk
from tkinter import ttk, messagebox
import sys

print(f"Python: {sys.version}")
print("Checking tkinter...")
try:
    root = tk.Tk()
    print("Tkinter root created.")
    root.destroy()
    print("Tkinter success!")
except Exception as e:
    print(f"Tkinter failed: {e}")
