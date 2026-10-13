# computer_use

GUI-level computer control. One tool, multiple actions.

## Actions

- screenshot - capture full screen (or a region) to a PNG file. Returns the file path.
- analyze_screen - screenshot + vision model. Prompt it with "where is the X button?"
  and it returns approximate pixel coordinates. This is how you get precise x/y.
- mouse_move(x, y) - move cursor to position
- mouse_click(x, y, button) - left (default), right, middle
- mouse_double_click(x, y)
- mouse_drag(x1, y1, x2, y2)
- mouse_scroll(x, y, amount) - positive = up, negative = down
- keyboard_type(text) - type a string
- keyboard_press(key) - single key: enter, tab, escape, f5, etc.
- keyboard_hotkey(keys) - combo: "ctrl+c", "alt+tab", "win+l"
- app_launch(name) - start a program by name or path

## To-do (not yet implemented)

- window_list - enumerate open windows (title, id, rect)
- window_focus(id) - bring a window to front
- window_minimize / maximize / close
- region_screenshot(x, y, w, h) - capture a sub-rectangle

## How precise positioning works

1. Take a full-screen screenshot.
2. Call analyze_screen with a prompt like:
   "What are the pixel coordinates (x, y) of the center of the [element]?"
3. The vision model returns approximate coordinates.
4. For higher precision, crop that region (region_screenshot, once implemented)
   and re-analyze the crop. Coordinates are relative to the crop, so offset
   them back to screen space.
5. Use those coordinates for mouse/keyboard actions.

The vision model is good to within ~5-15 px on a 1080p screen. For most
clicking that's fine. For pixel-perfect work (e.g. dragging a slider),
the crop-and-reanalyze loop tightens it.

## Dependencies

- pyautogui (mouse, keyboard, screenshot)
- Pillow (image cropping for region screenshots)
- Vision model via Ollama (analyze_screen) - same model as the main app

## Conventions

- All coordinates are in screen pixels, origin top-left.
- Screenshot files go to a temp dir, not the project.
- Actions return a short status string (e.g. "clicked at (452, 318)").
- analyze_screen returns the vision model's text response.
