import os

def change_md_to_mdx(input_file_path, output_file_path):
    if input_file_path.endswith(".md") and os.path.isfile(input_file_path):
        base = os.path.splitext(os.path.basename(input_file_path))[0]
        new_filename = base + ".mdx"
        dest_file_path = os.path.join(os.path.dirname(input_file_path), new_filename)

        try:
            os.rename(input_file_path, dest_file_path)
            print(f"Renamed {os.path.basename(input_file_path)} to {new_filename} in the same folder.")
        except Exception as e:
            print(f"Error renaming {os.path.basename(input_file_path)}: {e}")
    else:
        print(f"Skipping: {input_file_path} (not a markdown file or not a file)")

# Define your file path
input_file_path = "/Users/encord/Git/encord-docs-mint/agents-documentation/Reference/Task-Agents/Agents-Reference-Task-Agents.md" 

# Execute the function
change_md_to_mdx(input_file_path, "") # Outputting in the same folder