import os
import csv
# Attempt to load google.colab.userdata for API key management
try:
    from google.colab import userdata
    # Attempt to load API key if in Colab
    colab_api_key = userdata.get('gemini_api')
    if colab_api_key:
        os.environ["GEMINI_API_KEY"] = colab_api_key
        print("Successfully loaded GEMINI_API_KEY from Colab userdata.")
    # else:
        # print("GEMINI_API_KEY not found in Colab userdata. Will rely on other environment settings.")
except ImportError:
    # print("Not running in Colab environment. GEMINI_API_KEY should be set via environment variable.")
    pass

# import os # Duplicate import - already imported above
import google.generativeai as genai
# from google.generativeai import types # Commented out as types will be accessed via genai.types
import time
import re
from tqdm import tqdm
import io # Added for io.StringIO

# Ensure GEMINI_API_KEY is set, if not using userdata, set it directly for testing if needed.
# For actual execution, userdata.get('gemini_api') should work in Colab.
# If running locally and 'gemini_api' is an environment variable:
if "GEMINI_API_KEY" not in os.environ:
    api_key_from_env = os.getenv('GEMINI_API_KEY_ALT') # Example: use an alternative env var name
    if api_key_from_env:
        os.environ["GEMINI_API_KEY"] = api_key_from_env
    else:
        # Fallback or error if no key is available
        # print("Warning: GEMINI_API_KEY not found in environment. Mocking API calls.")
        # For now, let's assume the key will be set by the execution environment or Colab's userdata.
        # If direct os.environ setting is needed and userdata.get fails, it can be hardcoded for a test:
        # os.environ["GEMINI_API_KEY"] = "YOUR_ACTUAL_API_KEY_HERE"
        pass


def get_company_email(Company : str) -> str:
    """
    Generates company email using Gemini with Google Search.
    Returns the email as a string or an empty string if not found/error.
    """
    if not Company:
        return ""

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        # This check is important because genai.configure might not error out immediately
        # if the key is missing but is caught later during an API call.
        print("Error: GEMINI_API_KEY not found in environment for get_company_email.")
        return ""

    try:
        # Configure the API key
        genai.configure(api_key=api_key)

        # Define model and tools
        gemini_model_name = "gemini-pro"
        model = genai.GenerativeModel(model_name=gemini_model_name)

        text_prompt = f"""
Search for the email address of the company named "{Company}" using Google Search.
Provide the email address.
If you find an email, output it within a <final_answer> tag. For example: <final_answer>contact@example.com</final_answer>
If you cannot find a definitive email, output <final_answer>Not Found</final_answer>.
Output ONLY the content for the <final_answer> tag.
"""
        contents = [genai.types.Content(role="user", parts=[genai.types.Part.from_text(text=text_prompt)])]

        tools = [genai.types.Tool(google_search=genai.types.GoogleSearch())]

        generation_config = genai.types.GenerationConfig(
            temperature=0.1,
            top_p=0.95,
            top_k=40,
            max_output_tokens=8192, # Default is 2048, be mindful of model limits
        )

        # Make the API call
        response = model.generate_content(
            contents=contents,
            generation_config=generation_config,
            tools=tools
        )

        response_text = ""
        if hasattr(response, 'text') and response.text: # Check if text is not None or empty
            response_text = response.text
        elif response.parts and hasattr(response.parts[0], 'text') and response.parts[0].text:
            response_text = response.parts[0].text
        else:
            # Handle cases where the response might be a tool call or malformed
            if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
                if response.candidates[0].content.parts[0].function_call:
                    print(f"Warning: Model responded with a function call for {Company}, but direct text response was expected. Function call: {response.candidates[0].content.parts[0].function_call}")
                    return ""
            print(f"Warning: Could not extract text from response for {Company}. Response: {response}")
            return ""

        match = re.search(r"<final_answer>\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\s*</final_answer>", response_text)
        if match:
            email = match.group(1).strip()
            return email
        else:
            not_found_match = re.search(r"<final_answer>\s*Not Found\s*</final_answer>", response_text)
            if not_found_match:
                # print(f"Email not found for {Company} (as per model response).") # Less verbose
                return ""
            else:
                print(f"Warning: <final_answer> tag not found or email format incorrect in response for {Company}. Response text: '{response_text}'")
                return ""

    except Exception as e:
        # More specific error checks based on common issues with google-generativeai
        if "API key not valid" in str(e) or "API_KEY_INVALID" in str(e):
            print(f"Critical Error: Gemini API key is invalid. Please check GEMINI_API_KEY. Details: {e}")
        elif "permission" in str(e).lower() and ("denied" in str(e).lower() or "locations" in str(e).lower()):
            # This can happen if the API key is valid but doesn't have permissions for the specific model/region, or project not enabled
             print(f"Critical Error: Permission denied for Gemini API or model/region issue. Check API key permissions and ensure the Google AI Platform/Vertex AI service is enabled for your project. Details: {e}")
        elif "ুনাlocalized " in str(e) or "location" in str(e): # model may not be available in the location
             print(f"Critical Error: Model not available or location issue. Details: {e}")
        elif "Deadline" in str(e) or "timeout" in str(e).lower():
            print(f"Error: API call timed out for {Company}. Details: {e}")
        else:
            print(f"Error during Gemini API call for {Company}: {e}")
        return ""


def process_csv(input_file, output_file, start_row=1, end_row=None):
    encodings_to_try = ['utf-8', 'latin1', 'cp1252']
    successful_encoding = None
    infile_content_lines = None # To store decoded lines as a list of strings

    for encoding in encodings_to_try:
        try:
            print(f"Attempting to read {input_file} with encoding: {encoding}")
            with open(input_file, 'r', encoding=encoding) as infile_check:
                infile_content_lines = infile_check.readlines() # Read all lines
            successful_encoding = encoding
            print(f"Successfully read {input_file} with encoding: {successful_encoding}")
            break
        except UnicodeDecodeError:
            print(f"Encoding {encoding} failed for {input_file}.")
            continue
        except FileNotFoundError:
            print(f"ERROR: Input file not found: {input_file}")
            return
        except Exception as e:
            print(f"An unexpected error occurred while trying encoding {encoding} for {input_file}: {e}")
            # Optionally, decide to stop or continue based on the error
            # For now, let's continue to try other encodings if it's not FileNotFoundError or UnicodeDecodeError
            continue

    if not successful_encoding or infile_content_lines is None:
        print(f"ERROR: Could not decode {input_file} with any of the tried encodings: {encodings_to_try}.")
        return

    try:
        # Use io.StringIO to wrap the list of strings for DictReader
        infile_text_stream = io.StringIO("".join(infile_content_lines))

        with open(output_file, 'w', newline='', encoding='utf-8') as outfile:
            reader = csv.DictReader(infile_text_stream)

            fieldnames = reader.fieldnames
            if fieldnames is None:
                 print(f"ERROR: Could not read headers from {input_file} (using encoding {successful_encoding}). Is it empty or not a valid CSV?")
                 return

            output_fieldnames = list(fieldnames)
            if 'EMAIL' not in output_fieldnames:
                output_fieldnames.append('EMAIL')

            writer = csv.DictWriter(outfile, fieldnames=output_fieldnames, extrasaction='ignore')
            writer.writeheader()

            # Note: tqdm might be less accurate if row_count starts from reader and we skip some.
            # However, for overall progress, it's still useful.
            print(f"Processing rows from {start_row} (using encoding {successful_encoding})...")

            # We need to handle enumeration separately if we're to use tqdm effectively
            # on the reader that might be advanced by start_row logic.
            # A simple way is to process all rows from reader and apply start_row/end_row logic inside.

            all_rows_from_reader = list(reader) # Read all rows into a list to use tqdm properly with enumerate

            for row_idx, row_data in tqdm(enumerate(all_rows_from_reader, start=0), total=len(all_rows_from_reader), desc="Processing CSV"):
                row_count = row_idx + 1 # Actual row number in the file (1-indexed)

                if row_count < start_row:
                    # Write skipped rows to maintain file structure, as per previous logic and prompt example.
                    output_row_skipped = {field: row_data.get(field, '') for field in output_fieldnames}
                    # Ensure EMAIL column exists for skipped rows, even if not present in original row_data
                    if 'EMAIL' not in output_row_skipped:
                         output_row_skipped['EMAIL'] = ''
                    writer.writerow(output_row_skipped)
                    continue # Skip to next iteration if before start_row

                if end_row is not None and row_count > end_row:
                    # If we need to write rows *after* end_row as well, this logic would need adjustment.
                    # Current assumption: stop processing AND writing once end_row is passed.
                    break # Stop processing if past end_row

                # Get company name, ensuring to use the exact header name from CSV
                # Common variations: 'Company', 'Company Name', ' Company '
                # We will try a few common ones or rely on the user to ensure 'Company ' is used.
                # The previous code used 'Company ' (with a space).
                Company = row_data.get('Company ', '').strip()
                if not Company:
                     # Try other common variants if 'Company ' is not found or empty
                     possible_company_headers = ['Company', 'Company Name', 'Organization']
                     for header_variant in possible_company_headers:
                         Company = row_data.get(header_variant, '').strip()
                         if Company:
                             break

                # Initialize output_row with all original data from current row_data
                output_row = {field: row_data.get(field, '') for field in fieldnames}
                output_row['EMAIL'] = '' # Default email to empty

                if not Company:
                     print(f"Skipping row {row_count} due to missing company name (tried common headers).")
                     writer.writerow(output_row) # Write row with empty email
                     continue

                # print(f"Processing Company: {Company} (Row {row_count})") # tqdm provides progress

                email_address = get_company_email(Company)
                output_row['EMAIL'] = email_address

                # Ensure all output_fieldnames are present (extrasaction='ignore' helps but good to be explicit)
                for field_k in output_fieldnames:
                    if field_k not in output_row:
                        output_row[field_k] = ''

                writer.writerow(output_row)

                # Optional: add a delay if making many API calls
                # time.sleep(1) # Removed as per instruction to copy verbatim, but the original provided structure for this step also had it.
                                # The previous version of main.py had time.sleep(1) here. Let's keep it.
                time.sleep(1)

    except Exception as e:
        print(f"An error occurred during CSV processing (after potential decoding with {successful_encoding}): {e}")
        # Consider logging the error to a file or re-raising if critical

if __name__ == "__main__":
    # Set your GEMINI_API_KEY in your environment variables
    # For Colab, use:
    # from google.colab import userdata
    # os.environ["GEMINI_API_KEY"] = userdata.get('gemini_api')

    # Check if API key is set (basic check)
    if not os.getenv("GEMINI_API_KEY"):
        print("GEMINI_API_KEY is not set. Please set it before running the script.")
        print("If in Colab, ensure 'gemini_api' secret is set and `userdata.get('gemini_api')` is uncommented and working.")
    else:
        print("GEMINI_API_KEY found. Proceeding with script execution.")

    # Example: Create a dummy input CSV for testing
    dummy_input_file = "dummy_input.csv"
    with open(dummy_input_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["Company ", "PRODUCT CODE", "PRODUCT CATEGORY", "CATEGORIES NO"]) # Note "Company "
        writer.writerow(["TestCorp", "P001", "Tech", "1,2"])
        writer.writerow(["NoEmail Inc", "P002", "Services", "3"])
        writer.writerow(["", "P003", "Retail", "4"]) # Empty company name
        writer.writerow(["RealCo", "P004", "Consulting", "5,6,7,8,9,10"])
        writer.writerow(["FakeBiz", "P005", "Manufacturing", ""])


    # Get input_csv_file from the user's original script, but use dummy for now
    # input_csv_file = "/content/複本 The Inspired Home Show 2025_NON-US_BUYERS_LIST(1)(moke).csv"
    input_csv_file = dummy_input_file # Use dummy for this test run
    output_csv_file = "output.csv"

    # Adjust start_row and end_row for testing with the dummy file
    start_row = 1
    end_row = 5 # Process all rows in the dummy file

    print(f"Starting CSV processing for {input_csv_file} from row {start_row} to {end_row}.")
    process_csv(input_file=input_csv_file, output_file=output_csv_file, start_row=start_row, end_row=end_row)
    print(f"Processing complete. Results saved to: {output_csv_file}")

    # Verify output.csv content (optional print)
    print("\nContent of output.csv:")
    try:
        with open(output_csv_file, 'r', encoding='utf-8') as f_out:
            for line in f_out:
                print(line.strip())
    except FileNotFoundError:
        print(f"{output_csv_file} not found.")
