
with open(r'c:\Users\user\Downloads\universal-face-system\frontend\src\components\WorkoutFormAI.jsx', 'r', encoding='utf-8') as f:
    content = f.read()

start_index = content.find('const onResults = useCallback(')
end_index = content.find('}, []);', start_index) + 7
func_content = content[start_index:end_index]

open_braces = func_content.count('{')
close_braces = func_content.count('}')

print(f"Open: {open_braces}, Close: {close_braces}")
