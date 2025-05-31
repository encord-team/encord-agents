import os
import shutil

def convert_py_to_mdx_with_fences(input_base_dir, output_base_dir):
    """
    Converts all .py files found in input_base_dir (and its subdirectories)
    to .mdx files in output_base_dir, preserving the directory structure.
    Each .mdx file will have '```python' at the start and '```' at the end.
    __init__.py files are skipped.

    Args:
        input_base_dir (str): The root directory containing the .py files.
        output_base_dir (str): The root directory where the .mdx files will be saved.
    """
    print(f"Starting conversion from '{input_base_dir}' to '{output_base_dir}'")

    # Ensure the output directory is clean before starting
    if os.path.exists(output_base_dir):
        try:
            shutil.rmtree(output_base_dir)
            print(f"Cleared existing output directory: '{output_base_dir}'")
        except OSError as e:
            print(f"Error clearing output directory '{output_base_dir}': {e}. Please ensure it's not open or in use.")
            return # Exit if we can't clear the output directory
    
    os.makedirs(output_base_dir, exist_ok=True)
    print(f"Ensured output directory exists: '{output_base_dir}'")

    processed_count = 0
    skipped_count = 0
    error_count = 0

    for root, dirs, files in os.walk(input_base_dir):
        for filename in files:
            if filename.endswith(".py"):
                if filename == '__init__.py':
                    print(f"  Skipping __init__.py file: '{os.path.join(root, filename)}'")
                    skipped_count += 1
                    continue

                input_file_path = os.path.join(root, filename)

                # Determine the relative path from the input_base_dir
                relative_path = os.path.relpath(root, input_base_dir)

                # Construct the corresponding output directory path
                output_subdir = os.path.join(output_base_dir, relative_path)
                os.makedirs(output_subdir, exist_ok=True) # Ensure subdir exists

                # Construct the output .mdx file path
                output_file_name = filename.replace('.py', '.mdx')
                output_file_path = os.path.join(output_subdir, output_file_name)

                print(f"  Processing '{input_file_path}' -> '{output_file_path}'")

                try:
                    with open(input_file_path, 'r', encoding='utf-8') as infile:
                        content = infile.read()

                    with open(output_file_path, 'w', encoding='utf-8') as outfile:
                        outfile.write('```python\n')
                        outfile.write(content)
                        outfile.write('\n```\n') # Add a newline before closing fence for better formatting

                    processed_count += 1
                except Exception as e:
                    print(f"  ERROR: Could not process '{input_file_path}': {e}")
                    error_count += 1

    print(f"\nConversion complete!")
    print(f"  Files processed: {processed_count}")
    print(f"  Files skipped (__init__.py): {skipped_count}")
    print(f"  Files with errors: {error_count}")
    print(f"Output saved to: '{output_base_dir}'")


if __name__ == "__main__":
    # Define your input and output directories here
    input_folder = '/Users/encord/Git/encord-agents/docs/code_examples'
    output_folder = '/Users/encord/Git/encord-docs-mint/snippets/code_examples' # This will be created/cleared

    convert_py_to_mdx_with_fences(input_folder, output_folder)