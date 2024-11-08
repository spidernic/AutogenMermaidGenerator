
'''
YAML-Based Project Documentation REPORTING Tool 

This script is a command-line interface tool designed to convert the JSON into markdown

Author Information:
- Author: Nic Cravino
- Email: spidernic@me.com / ncravino@mac.com
- LinkedIn: https://www.linkedin.com/in/nic-cravino
- Date: October 26, 2024

'''
import json
import os

# Directories for input and output
input_folder = './output/'
output_folder = './reports/'

# Ensure output directory exists
os.makedirs(output_folder, exist_ok=True)

def print_markdown(output_data, output_path):
    with open(output_path, 'w') as f:
        # Write summary
        f.write("# Summary\n\n")
        f.write(output_data["SUMMARY"] + "\n\n")

        # Write DFD
        f.write("## Data Flow Diagram\n\n")
        f.write(output_data["DFD"] + "\n\n")

        # Write ERD
        f.write("## Entity Relationship Diagram\n\n")
        f.write(output_data["ERD"] + "\n\n")

        # Write Data Dictionary in table format
        f.write("## Data Dictionary\n\n")
        f.write("| Component | Field | Description |\n")
        f.write("|-----------|-------|-------------|\n")
        for component, fields in output_data["DataDictionary"].items():
            for field, description in fields.items():
                f.write(f"| {component} | {field} | {description} |\n")
        f.write("\n")

        # Write Code Context in table format
        f.write("## Code Context\n\n")
        f.write("| Function | Description | Error Handling | Output |\n")
        f.write("|----------|-------------|----------------|--------|\n")
        for function, details in output_data["codecontext"].items():
            description = details.get("Description", "N/A")
            error_handling = details.get("Error Handling", "N/A")
            output = details.get("Output", "N/A")
            f.write(f"| {function} | {description} | {error_handling} | {output} |\n")
        f.write("\n")

        # Write Scan Information in table format
        f.write("## Scan Information\n\n")
        f.write("| Filename | File Path | Scan Date | Scan Duration (s) | MD5 Hash | Total Tokens | Total Cost (USD) | Lines of Code | Scan Type |\n")
        f.write("|----------|-----------|-----------|------------------|----------|--------------|-----------------|---------------|-----------|\n")
        f.write(f"| {output_data['filename']} | {output_data['file_path']} | {output_data['scan_date']} | {output_data['scan_duration']:.2f} | {output_data['md5_hash']} | {output_data['total_tokens']} | ${output_data['total_cost']:.5f} | {output_data['lines_of_code']} | {output_data['scan_type']} |\n")

if __name__ == "__main__":
    # Iterate over JSON files in the input folder
    for filename in os.listdir(input_folder):
        if filename.endswith('.json'):
            input_path = os.path.join(input_folder, filename)
            output_filename = filename.replace('.json', '.md')
            output_path = os.path.join(output_folder, output_filename)

            # Load JSON data from the file
            with open(input_path, 'r') as json_file:
                output_data = json.load(json_file)

            # Generate markdown report
            print_markdown(output_data, output_path)
