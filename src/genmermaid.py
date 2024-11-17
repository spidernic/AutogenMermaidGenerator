'''
YAML-Based Project Documentation Tool using OpenAI & Microsoft Autogen Agents (v0.3.1)

This script is a command-line interface tool designed to generate project documentation by scanning a repository, analyzing code, and producing detailed documentation. It utilizes OpenAI models and Microsoft Autogen Agents to generate output such as Mermaid.js diagrams, JSON reports, and feedback.

Key Features:
- YAML-Based Analysis for customizable configurations.
- Multi-Agent Collaboration to generate, review, and refine documentation.
- Generates visual diagrams (ERD, DFD) using Mermaid.js.
- Converts JSON reports to Markdown for easier sharing and readability.
- Provides error logging and vulnerability reporting for future analysis.

Installation and Setup:
1. Clone the repository and navigate to the directory.
2. Install the dependencies using pip.
3. Set the required environment variables in a `.env` file.

License: Apache License 2.0
- Freedom to use, modify, and distribute with attribution.
- No warranties or liability are provided by the authors.

Author Information:
- Author: Nic Cravino
- Email: spidernic@me.com 
- LinkedIn: https://www.linkedin.com/in/nic-cravino
- Date: October 26, 2024

'''

# Import necessary Libraries for the scanner functionality
from autogen import AssistantAgent, UserProxyAgent, GroupChat, GroupChatManager, OpenAIWrapper, gather_usage_summary
import os
import yaml
import sys
from dotenv import load_dotenv
import chardet
import json
from datetime import datetime, timedelta
import random
import hashlib
import argparse
import tiktoken
import logging

# Constants for file paths and model configuration
reportsdir = './output/'                                                              # Location to store JSON output (one per file)
feedbackdir = './feedback/'  
logsdir = './logs/'
yamlfile = './yaml/promptsmermaid.yml'
fecha1 = datetime.now().strftime("%Y%m%dT%H%M%S")

# Initialize folders
os.makedirs(reportsdir, exist_ok=True)
os.makedirs(feedbackdir, exist_ok=True)
os.makedirs(logsdir, exist_ok=True)

# Initialize Logging Mechanism
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(f"{logsdir}scan_{fecha1}.log"),
        logging.StreamHandler()
    ]
)

# Function to parse command-line arguments (better than doing it in main, scalable)
def parse_arguments():
    parser = argparse.ArgumentParser(description='Read and document source code repository')
    parser.add_argument('repo_to_scan', type=str, help='Folder to scan')
    return parser.parse_args()

# Location to store feedback JSON output for improvement
temperature = 0.2
context_size = 120000
semilla = random.randint(100, 999)

############################################## CODE NOT SERVICEABLE BEYOND THIS LINE ##########################################################

# Function to select the YAML file based on parameter

# Load YAML file containing prompts
def load_yaml_file(yaml_file_path):
    with open(yaml_file_path, 'r', encoding='utf-8') as file:
        return yaml.safe_load(file)

# Import environmental variables
load_dotenv(override=True)
api_key = os.getenv('OPEN_AI_API_KEY2')                                               # Use the 'Project' API key 
model_name = os.getenv('MODEL_NAME')                                                  # I select the model in the YAML file

# Base config for OpenAI
config_list_openai = [
    {"model": model_name, "api_key": api_key}
]
llm_config = {
    "seed": semilla,                                                                   # change the seed for different trials
    "config_list": config_list_openai,
    "timeout": 60000,
    "temperature": temperature,
    "response_format": {'type': "json_object"},                                        # This is KEY, only GPT-4o is consistent in JSON, I tried OSS ones (All Mistral ones, llama 3, and Hermes variants, and even GPT-4o-mini, but these are NOT consistent, they deviate.
}

# Initialize variables
sum_total_tokens, sum_total_cost, sum_error = 0, 0.0, 0
encoding = tiktoken.get_encoding("cl100k_base")

# Function to read a file and determine its encoding
def read_file(file_path):
    try:
        with open(file_path, 'rb') as f:
            raw_data = f.read()
        encoding = chardet.detect(raw_data)['encoding']
        return raw_data.decode(encoding)
    except UnicodeDecodeError:
        try:
            with open(file_path, "r", encoding='Latin-1') as f:                         # I added latin since the chardet library is for some reason ignoring this one . weird.
                raw_data = f.read()
            return raw_data
        except Exception:
            return None

# Function to count tokens in a given text (uses tiktoken and cl100k_base)
def count_tokens(text, filename):
    global context_size
    try:
        num_tokens = encoding.encode(text)
        if len(num_tokens) > context_size:
            raise ValueError(f'Token limit exceeded: {len(num_tokens)} tokens (limit is {context_size} tokens)')
    except ValueError as e:
        fecha = datetime.now().strftime("%Y%m%dT%H%M%S")
        error_message = f"ERROR: [Timestamp: {fecha}] - [File Size limit exceeded: {len(num_tokens)} tokens (limit is {context_size} tokens)]"
        output_filename = f"{reportsdir}/TOKEN_SIZE_ERROR_{filename}_{fecha}.txt"
        with open(output_filename, "w") as f:
            f.write(error_message)
        logging.error(error_message)
        return False
    return True

# Function to calculate MD5 hash of a file's contents (for integrity and non-repudiation)
def calculate_md5(file_path):
    hasher = hashlib.md5()
    with open(file_path, "rb") as f:
        buf = f.read()
        hasher.update(buf)
    return hasher.hexdigest()

# Function to save the vulnerability report in JSON format (here it appends the value-keys below, to the value-keys already generated as per the YAML prompt and YAML examples.)
def save_vulnerability_report(vuln_data, filename, path, duration, md5, total_tokens, total_cost, lines_of_code, target):
    global reportsdir
    vuln_data.update({
        'filename': filename,
        'file_path': path,
        'scan_date': datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        'scan_duration': duration.total_seconds(),
        'md5_hash': md5,
        'total_tokens': total_tokens,
        'total_cost': total_cost,
        'lines_of_code': lines_of_code,
        'scan_type': target
    })
    report_filename = f"scan_report_{filename}_{datetime.now().strftime('%Y%m%dT%H%M%S')}.json"
    report_path = os.path.join(reportsdir, report_filename)
    with open(report_path, "w") as f:
        json.dump(vuln_data, f, indent=4)

# Save JSON with the challenge (if any) from the adversary agent. To be used for manual prompt engineeringg / improvement.
def save_feedback_report(vuln_data):
    global feedbackdir
    report_filename = f"feedback_report_{datetime.now().strftime('%Y%m%dT%H%M%S')}.json"
    report_path = os.path.join(feedbackdir, report_filename)
    with open(report_path, "w") as f:
        json.dump(vuln_data, f, indent=4)

# Function to format the total duration of the scan
def format_duration(total_duration):
    total_seconds = int(total_duration.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours} hours, {minutes} minutes, {seconds} seconds"

# Function to print a summary banner after the scan is completed
def banner_full(vueltas, total_duration, sum_lines_of_code, sum_total_tokens, sum_total_cost, sum_error, target):
    delta = format_duration(total_duration)
    summary1 = f'''
[ Script Finished ] {'*' * 103}
[ {vueltas} files scanned for {target} ] [ {sum_lines_of_code:,} lines of code ] [ Total Duration: {delta} ]
[ Total Tokens: {sum_total_tokens:,} ] [ Total Cost in USD: #{sum_total_cost:.2f} ]
[ Statistics ] [ ERRORS: {sum_error:,} ]
{'*' * 123}'''
    return summary1


# Function to print a concise summary banner during the scan
def banner_small(vueltas, total_duration, sum_lines_of_code, sum_total_tokens, sum_total_cost, sum_error ):
    delta = format_duration (total_duration)
    summary1 = f'''
{'*' * 150}
[ Scan Duration: {delta} ] [ Total Tokens: {sum_total_tokens:,}] [Total Cost (USD): {sum_total_cost: 2f} ] [ ERROR: {sum_error:,} ]
{'*' * 150}
'''
    return (summary1)

# Main function to initiate the scanning process
def main(repo_to_scan):
    global prompts, sum_total_tokens, sum_total_cost, sum_error
    
    try:
        yaml_file_path = yamlfile
        prompts = load_yaml_file(yaml_file_path)
    except (FileNotFoundError, yaml.YAMLError) as e:
        logging.error(f"Error loading YAML file: {e}")
        return
    
    if not os.path.exists(repo_to_scan):
        logging.error(f"Repository not found: {repo_to_scan}")
        return

    vueltas, total_duration, sum_lines_of_code = 0, timedelta(0), 0
    #os.system('clear')
    target = prompts["prompts"]["target"].upper()
    print(f"{'*' * 104}\n{target}\n{'*' * 104}")

    for dirpath, dirnames, filenames in os.walk(repo_to_scan):
        if 'ipynb_checkpoints' in dirpath:                                                                                       # Here we skip any folder that we don't fancy scanning
            logging.info("FOLDER SKIPPED: - ipynb_checkpoints: %s", dirpath)
            continue
        for filename in filenames:                                                                                               # Here we skip any file extension that we don't fancy scanning
            if '.egg' in filename:
                logging.info("FILE SKIPPED: - .egg: %s", filename)
                continue

            file_path = os.path.join(dirpath, filename)
            if os.path.isfile(file_path):
                total_tokens, total_cost = 0, 0.0
                vueltas += 1

                try:
                    code = read_file(file_path)
                except Exception as e:
                    sum_error += 1
                    fecha = datetime.now().strftime("%Y%m%dT%H%M%S")
                    error_message = f"ERROR: [Timestamp: {fecha}] - [Target file corrupted: {file_path} - Error details: {e}]"
                    output_filename = f"{reportsdir}READ_ERROR_{fecha}_{filename}.txt"
                    with open(output_filename, "w") as f:
                        f.write(error_message)
                    logging.error(error_message)
                    continue

                if not count_tokens(code, filename):
                    sum_error += 1
                    continue

                # Further processing
                lines_of_code = len(code.splitlines())
                sum_lines_of_code += lines_of_code
                md5 = calculate_md5(file_path)
                
                # Define reference and tag inference start-time
                reference = f"[md5]_{datetime.now().strftime('%Y%m%dT%H%M%S')}_{filename}"
                start_time = datetime.now()

                # Populating agents system messages from YAML config file
                example_schema = prompts["prompts"]["example_schema"]
                output_example = prompts["prompts"]["output_example"]
                example_mermaid = prompts["prompts"]["example_mermaid"]
                system_message_manager_agent = f"{prompts['prompts']['core_manager_agent'].format(target=target, code=code,  example_mermaid=example_mermaid, output_example=output_example, example_schema=example_schema)}"
                system_message_core_coder_agent = f"{prompts['prompts']['core_coder_agent'].format(filename=filename, example_mermaid=example_mermaid, output_example=output_example, reference=reference, code=code, target=target,  example_schema=example_schema)}"

                # Define Microsoft Autogen Agents (version 0.2.3)
                pod_agents = {
                    "core_manager_agent": UserProxyAgent(
                        name="core_manager_agent",
                        human_input_mode="NEVER",
                        max_consecutive_auto_reply=6,
                        is_termination_msg=lambda x: "TERMINATE" in x.get("content", ""),
                        llm_config=llm_config,
                        code_execution_config=False,
                        system_message=system_message_manager_agent
                    ),
                    "core_coder_agent": AssistantAgent(
                        name="core_coder_agent",
                        max_consecutive_auto_reply=6,
                        is_termination_msg=lambda x: json.loads(x.get("content", "{}")) .get("NEXTSTEP") == "TERMINATE",
                        llm_config=llm_config,
                        code_execution_config=False,
                        system_message=system_message_core_coder_agent
                    )
                }

                # Define GroupChat Structure for Microsoft Autogen (version 0.2.3)
                groupchat = GroupChat(
                    agents=list(pod_agents.values()),
                    messages=[],
                    max_round=20,
                    speaker_selection_method="auto",
                    allow_repeat_speaker=False
                )

                # Add a built-in manager to ensure chat transition
                manager = GroupChatManager(groupchat=groupchat, llm_config=llm_config)

                # Minimal console status
                print(f"\n[{vueltas}] - scanning {file_path} for {target}")

                # Start GroupChat
                try:
                    pod_agents["core_manager_agent"].initiate_chat(
                        manager, silent=False,
                        code_execution_config=False,
                        max_rounds=12,
                        message=prompts["prompts"]["autogen_manager_agent"]
                        )
                except Exception as e:
                    logging.error(f"Agent initiation failed: {e}")
                    continue

                end_time = datetime.now()

                # Track Token Usage and cost per agent
                total_usage_list = []
                for podagent in pod_agents:
                    if pod_agents[podagent].get_total_usage() is not None:
                        total_usage_list.append(pod_agents[podagent].get_total_usage())

                for usage in total_usage_list:
                    for key, value in usage.items():
                        if isinstance(value, dict):
                            total_tokens = value.get("total_tokens", 0)
                            total_cost = value.get("cost", 0.00000)
                            break

                # Store Grand Totals
                sum_total_tokens += total_tokens
                sum_total_cost += total_cost

                # Track Duration for stats
                duration = abs(start_time - end_time)
                total_duration += duration

                # Collect feedback for agent self-training (manual)
                for message2 in groupchat.messages:
                    if message2["name"] == pod_agents["core_manager_agent"].name:
                        try:
                            salida2 = json.loads(message2["content"])
                            if "NEXTSTEP" in salida2:
                                feedback = salida2["NEXTSTEP"]
                                if feedback == "REVISE":
                                    save_feedback_report(salida2)
                        except json.JSONDecodeError:
                            continue

                # Parse Conversation Log in reverse for the last valid entry
                for message in reversed(groupchat.messages):
                    if message["name"] == pod_agents["core_coder_agent"].name:
                        try:
                            salida = json.loads(message["content"])
                            if "SUMMARY" in salida and "DataDictionary" in salida and "DFD" in salida and "ERD" in salida and "codecontext" in salida:
                                save_vulnerability_report(salida, filename, dirpath, duration, md5, total_tokens, total_cost, lines_of_code, target)
                                break
                        except json.JSONDecodeError:
                            logging.error("READ-JSON-ERROR-GROUPCHAT-MSG", filename)
                            continue

                # Print Stats per file analyzed
                # Print Stats per file analyzed
                print(banner_small(vueltas, total_duration, sum_lines_of_code, sum_total_tokens, sum_total_cost, sum_error))

    # Print Final Stats
    adios = banner_full(vueltas, total_duration, sum_lines_of_code, sum_total_tokens, sum_total_cost, sum_error, target)
    print(adios)
    chau = f'''Tally: {vueltas}, Duration: {total_duration}, LoC: {sum_lines_of_code}, Tokens: {sum_total_tokens}, Cost: ${sum_total_cost}, ERROR: {sum_error}, TARGET: {target}'''
    logging.info( chau)

# Entry point for the script
if __name__ == "__main__":
    args = parse_arguments()
    repo_to_scan = args.repo_to_scan
    
    if not os.path.isdir(repo_to_scan):
        logging.error(f"Invalid directory specified: {repo_to_scan}")
        sys.exit(1)

    main(repo_to_scan)
