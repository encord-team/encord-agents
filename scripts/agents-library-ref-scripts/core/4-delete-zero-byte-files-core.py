import os

def delete_zero_byte_file(file_path):
    try:
        # Check if the file exists and is a file
        if os.path.isfile(file_path):
            # Check if the file size is zero bytes
            if os.path.getsize(file_path) == 0:
                os.remove(file_path)  # Delete the file
                print(f"Deleted: {file_path}")
            else:
                print(f"Skipped (not zero bytes): {file_path}")
        else:
            print(f"Skipped (not a file): {file_path}")
    except Exception as e:
        print(f"An error occurred while processing {file_path}: {e}")

if __name__ == "__main__":
    file_to_process = '/Users/encord/Git/encord-docs-mint/agents-documentation/Reference/Core/Agents-Reference-Core.md'  # Change to your input file path
    delete_zero_byte_file(file_to_process)