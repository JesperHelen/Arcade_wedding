from pynput import keyboard

print("Lyssnar på ALLA tangenttryck...")
print("Tryck ESC för att avsluta\n")

def on_press(key):
    try:
        print(f"Tangent tryckt: {key.char}")
    except AttributeError:
        print(f"Specialtangent: {key}")

def on_release(key):
    if key == keyboard.Key.esc:
        print("Avslutar.")
        return False

with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
    listener.join()
