import csv

import project_files

import json
from sklearn.metrics import confusion_matrix, accuracy_score, precision_score, recall_score, f1_score

# def get_all_matching_responses():
#     models = ["claude-sonnet-4.6", "gemini-3-flash-preview", "gpt-5.4-nano", "llama-3.3-70b-instruct"]
#     with open("./project_files.json", 'r', encoding='utf-8') as pf:
#         project_files = json.load(pf)

#     for project_key in project_files:
#         print (f"\n--- For project: {project_key} ---\n")

#         project = project_files[project_key]
#         for model in models:
#             # Load the questions JSON file
#             questions_json_file = project["questions_json_file"]
#             with open(questions_json_file, 'r', encoding='utf-8') as pf:
#                 questions = json.load(pf)
            
#             counter = 0
#             # Save question[0]["answer"] as a variable
#             for idx in range(0, 60): 
#                 ground_truth_answer = questions[idx]["answer"]
#                 category = questions[idx]["category"]

#                 try:
#                     # Load the results JSON file
#                     results_file = f"{project["parent_directory"]}/results/{model}/{category}/{idx+1}.json"

#                     with open(results_file, 'r', encoding='utf-8') as rf:
#                         result = json.load(rf)

#                     if (result["response"]["answer"] == ground_truth_answer):
#                         counter += 1 
#                 except FileNotFoundError as e:
#                     print(e)
#                     pass # Basically skipping that entry
            
#             print(f"Number of correct responses for {model}: {counter}")

# def generate_confusion_matrix_for_all_projects():
#     models = ["claude-sonnet-4.6", "gemini-3-flash-preview", "gpt-5.4-nano", "llama-3.3-70b-instruct"]
#     with open("./project_files.json", 'r', encoding='utf-8') as pf:
#         project_files = json.load(pf)

#     for project_key in project_files:
#     # project_key = list(project_files.keys())[0]
#         print (f"\n--- For project: {project_key} ---\n")

#         project = project_files[project_key]

#         for model in models:
#             counter = 0
#             actual_responses = ["N/A"] * 60
#             predicted_responses = ["N/A"] * 60

#             # Load the questions JSON file
#             questions_json_file = project["questions_json_file"]
#             with open(questions_json_file, 'r', encoding='utf-8') as pf:
#                 questions = json.load(pf)
            
#             # Save question[0]["answer"] as a variable
#             for idx in range(0, 60): 
#                 actual_responses[idx] = questions[idx]["answer"]
#                 category = questions[idx]["category"]

#                 try:
#                     # Load the results JSON file
#                     results_file = f"{project["parent_directory"]}/results/{model}/{category}/{idx+1}.json"

#                     with open(results_file, 'r', encoding='utf-8') as rf:
#                         result = json.load(rf)
#                         predicted_responses[idx] = result["response"]["answer"]
#                     if (result["response"]["answer"] == questions[idx]["answer"]):
#                         counter += 1
#                 except FileNotFoundError as e:
#                     print(e)
#                     predicted_responses[idx] = "N/A"
#                     pass # Basically skipping that entry
            
#             print(f"Number of total correct responses for {model}: {counter}")
#             cm = confusion_matrix(actual_responses, predicted_responses)
#             print(cm)       

# def retrieve_response_numbers_for_all_models_per_category():
#     models = ["claude-sonnet-4.6", "gemini-3-flash-preview", "gpt-5.4-nano", "llama-3.3-70b-instruct"]
#     with open("./project_files.json", 'r', encoding='utf-8') as pf:
#         project_files = json.load(pf)

#     for project_key in project_files:
#         print (f"\n--- For project: {project_key} ---\n")

#         actual_responses = {
#             "component_datasheet": [],
#             "spice_behaviour": [],
#             "theory_layout": [],
#         }

#         predicted_responses = {
#             "component_datasheet": [],
#             "spice_behaviour": [],
#             "theory_layout": [],
#         }

#         project = project_files[project_key]

#         for model in models:
#             counter = 0

#             # Load the questions JSON file
#             questions_json_file = project["questions_json_file"]
#             with open(questions_json_file, 'r', encoding='utf-8') as pf:
#                 questions = json.load(pf)
            
#             # Save question[0]["answer"] as a variable
#             for idx in range(0, 60): 
#                 category = questions[idx]["category"]

#                 actual_responses_list = actual_responses[category]
#                 actual_responses_list.append(questions[idx]["answer"])
#                 actual_responses[category] = actual_responses_list

#                 try:
#                     # Load the results JSON file
#                     results_file = f"{project["parent_directory"]}/results/{model}/{category}/{idx+1}.json"

#                     with open(results_file, 'r', encoding='utf-8') as rf:
#                         result = json.load(rf)

#                         predicted_responses_list = predicted_responses[category]
#                         predicted_responses_list.append(result["response"]["answer"])
#                         predicted_responses[category] = predicted_responses_list

#                     if (result["response"]["answer"] == questions[idx]["answer"]):
#                         counter += 1
#                 except FileNotFoundError as e:
#                     print(e)

#                     predicted_responses_list = predicted_responses[category]
#                     predicted_responses_list.append("N/A")
#                     predicted_responses[category] = predicted_responses_list
            
#             # print(f"Number of total correct responses for {model}: {counter}")
#             # cm = confusion_matrix(actual_responses, predicted_responses)
#             # print(cm)  

#         for category in actual_responses.keys():
#             cm = confusion_matrix(actual_responses[category], predicted_responses[category])
#             print(f"Confusion matrix for category: {category}\n", cm)  

# def retrieve_responses_per_model_per_project():
#     models = ["claude-sonnet-4.6", "gemini-3-flash-preview", "gpt-5.4-nano", "llama-3.3-70b-instruct"]
#     with open("./project_files.json", 'r', encoding='utf-8') as pf:
#         project_files = json.load(pf)

#     for project_key in project_files:
#         print (f"\n--- For project: {project_key} ---\n")

#         for model in models:

#             actual_responses = []

#             predicted_responses = []
#             project = project_files[project_key]

#             counter = 0

#             # Load the questions JSON file
#             questions_json_file = project["questions_json_file"]
#             with open(questions_json_file, 'r', encoding='utf-8') as pf:
#                 questions = json.load(pf)
            
#             # Save question[0]["answer"] as a variable
#             for idx in range(0, 60): 
#                 category = questions[idx]["category"]
#                 actual_responses.append(questions[idx]["answer"])

#                 try:
#                     # Load the results JSON file
#                     results_file = f"{project["parent_directory"]}/results/{model}/{category}/{idx+1}.json"

#                     with open(results_file, 'r', encoding='utf-8') as rf:
#                         result = json.load(rf)
#                         predicted_responses.append(result["response"]["answer"])

#                     if (result["response"]["answer"] == questions[idx]["answer"]):
#                         counter += 1
#                 except FileNotFoundError as e:
#                     print(e)
#                     predicted_responses.append("N/A")
            
#             print(f"Number of total correct responses for {model}: {counter}")
#             cm = confusion_matrix(actual_responses, predicted_responses)

#             # Calculate metrics
#             accuracy = accuracy_score(actual_responses, predicted_responses)
#             precision = precision_score(actual_responses, predicted_responses, pos_label = "YES", average="macro")
#             recall = recall_score(actual_responses, predicted_responses, pos_label = "YES", average="macro")
#             f1 = f1_score(actual_responses, predicted_responses, pos_label = "YES", average="macro")

#             print(f'Accuracy: {accuracy}')
#             print(f'Precision: {precision}')
#             print(f'Recall: {recall}')
#             print(f'F1 Score: {f1}')

#             # print(cm)  

#         # for category in actual_responses.keys():
#         #     cm = confusion_matrix(actual_responses[category], predicted_responses[category])
#         #     print(f"Confusion matrix for category: {category}\n", cm)  

# def retrieve_dry_run_responses_per_model_per_project():
#     models = ["claude-sonnet-4.6", "gemini-3-flash-preview", "gpt-5.4-nano", "llama-3.3-70b-instruct"]
#     with open("./project_files.json", 'r', encoding='utf-8') as pf:
#         project_files = json.load(pf)

#     for project_key in project_files:
#         print (f"\n--- For project: {project_key} ---\n")

#         for model in models:

#             actual_responses = []

#             predicted_responses = []
#             project = project_files[project_key]

#             counter = 0

#             # Load the questions JSON file
#             questions_json_file = project["questions_json_file"]
#             with open(questions_json_file, 'r', encoding='utf-8') as pf:
#                 questions = json.load(pf)
            
#             # Save question[0]["answer"] as a variable
#             for idx in range(0, 60): 
#                 category = questions[idx]["category"]
#                 actual_responses.append(questions[idx]["answer"])

#                 try:
#                     # Load the results JSON file
#                     results_file = f"{project["parent_directory"]}/dry_run/{model}/{category}/{idx+1}.json"

#                     with open(results_file, 'r', encoding='utf-8') as rf:
#                         result = json.load(rf)
#                         predicted_responses.append(result["response"]["answer"])

#                     if (result["response"]["answer"] == questions[idx]["answer"]):
#                         counter += 1
#                 except FileNotFoundError as e:
#                     print(e)
#                     predicted_responses.append("N/A")
            
#             print(f"Number of total correct responses for {model}: {counter}")
#             cm = confusion_matrix(actual_responses, predicted_responses)

#             # Calculate metrics
#             accuracy = accuracy_score(actual_responses, predicted_responses)
#             precision = precision_score(actual_responses, predicted_responses, pos_label = "YES", average="macro")
#             recall = recall_score(actual_responses, predicted_responses, pos_label = "YES", average="macro")
#             f1 = f1_score(actual_responses, predicted_responses, pos_label = "YES", average="macro")

#             print(f'Accuracy: {accuracy}')
#             print(f'Precision: {precision}')
#             print(f'Recall: {recall}')
#             print(f'F1 Score: {f1}')

#             # print(cm)  

#         # for category in actual_responses.keys():
#         #     cm = confusion_matrix(actual_responses[category], predicted_responses[category])
#         #     print(f"Confusion matrix for category: {category}\n", cm)  

# def retrieve_all_responses_per_model():
#     models = ["claude-sonnet-4.6", "gemini-3-flash-preview", "gpt-5.4-nano", "llama-3.3-70b-instruct"]

#     for model in models: 
#         print (f"\n--- For model: {model} ---\n")

#         with open("./project_files.json", 'r', encoding='utf-8') as pf:
#             project_files = json.load(pf)

#         for project_key in project_files:
#             # print (f"\n--- For project: {project_key} ---\n")

#             actual_responses = []

#             predicted_responses = []
#             project = project_files[project_key]

#             counter = 0

#             # Load the questions JSON file
#             questions_json_file = project["questions_json_file"]
#             with open(questions_json_file, 'r', encoding='utf-8') as pf:
#                 questions = json.load(pf)
            
#             # Save question[0]["answer"] as a variable
#             for idx in range(0, 60): 
#                 category = questions[idx]["category"]
#                 actual_responses.append(questions[idx]["answer"])

#                 try:
#                     # Load the results JSON file
#                     results_file = f"{project["parent_directory"]}/results/{model}/{category}/{idx+1}.json"

#                     with open(results_file, 'r', encoding='utf-8') as rf:
#                         result = json.load(rf)
#                         predicted_responses.append(result["response"]["answer"])

#                     if (result["response"]["answer"] == questions[idx]["answer"]):
#                         counter += 1
#                 except FileNotFoundError as e:
#                     print(e)
#                     predicted_responses.append("N/A")
            
#             print(f"Number of total correct responses for {project_key}: {counter}")
#             cm = confusion_matrix(actual_responses, predicted_responses)

#             # Calculate metrics
#             accuracy = accuracy_score(actual_responses, predicted_responses)
#             precision = precision_score(actual_responses, predicted_responses, pos_label = "YES", average="macro")
#             recall = recall_score(actual_responses, predicted_responses, pos_label = "YES", average="macro")
#             f1 = f1_score(actual_responses, predicted_responses, pos_label = "YES", average="macro")

#             print(f'Accuracy: {accuracy}')
#             print(f'Precision: {precision}')
#             print(f'Recall: {recall}')
#             print(f'F1 Score: {f1}')

#             # print(cm)  

#         # for category in actual_responses.keys():
#         #     cm = confusion_matrix(actual_responses[category], predicted_responses[category])
#         #     print(f"Confusion matrix for category: {category}\n", cm)  

# def retrieve_all_dry_run_responses_per_model():
#     models = ["claude-sonnet-4.6", "gemini-3-flash-preview", "gpt-5.4-nano", "llama-3.3-70b-instruct"]

#     for model in models: 
#         print (f"\n--- For model: {model} ---\n")

#         with open("project_files.json", 'r', encoding='utf-8') as pf:
#             project_files = json.load(pf)

#         for project_key in project_files:
#             # print (f"\n--- For project: {project_key} ---\n")

#             actual_responses = []

#             predicted_responses = []
#             project = project_files[project_key]

#             counter = 0

#             # Load the questions JSON file
#             questions_json_file = project["questions_json_file"]
#             with open(questions_json_file, 'r', encoding='utf-8') as pf:
#                 questions = json.load(pf)
            
#             # Save question[0]["answer"] as a variable
#             for idx in range(0, 15): 
#                 category = questions[idx]["category"]
#                 actual_responses.append(questions[idx]["answer"])

#                 try:
#                     # Load the results JSON file
#                     results_file = f"{project["parent_directory"]}/dry_run/{model}/{category}/{idx+1}.json"

#                     with open(results_file, 'r', encoding='utf-8') as rf:
#                         result = json.load(rf)
#                         predicted_responses.append(result["response"]["answer"])

#                         if (result["response"]["answer"] == questions[idx]["answer"]):
#                             counter += 1
#                 except FileNotFoundError as e:
#                     print(e)
#                     predicted_responses.append("N/A")
            
#             print(f"Number of total correct responses for {project_key}: {counter}")
#             cm = confusion_matrix(actual_responses, predicted_responses)

#             # Calculate metrics
#             accuracy = accuracy_score(actual_responses, predicted_responses)
#             precision = precision_score(actual_responses, predicted_responses, pos_label = "YES", average="macro")
#             recall = recall_score(actual_responses, predicted_responses, pos_label = "YES", average="macro")
#             f1 = f1_score(actual_responses, predicted_responses, pos_label = "YES", average="macro")

#             print(f'Accuracy: {accuracy}')
#             print(f'Precision: {precision}')
#             print(f'Recall: {recall}')
#             print(f'F1 Score: {f1}')

#             # print(cm)  

#         # for category in actual_responses.keys():
#         #     cm = confusion_matrix(actual_responses[category], predicted_responses[category])
#         #     print(f"Confusion matrix for category: {category}\n", cm)  

# def write_responses_to_csv():
#     models = ["claude-sonnet-4.6", "gemini-3-flash-preview", "gpt-5.4-nano", "llama-3.3-70b-instruct"]

#     for model in models: 
#         print (f"\n--- For model: {model} ---\n")

#         with open("./project_files.json", 'r', encoding='utf-8') as pf:
#             project_files = json.load(pf)

#         for project_key in project_files:
#             # print (f"\n--- For project: {project_key} ---\n")
#             with open(f'{model}_{project_key}.csv', 'w', newline='') as file:
#                 fields = ['Model', 'Question', 'Category', 'Actual_Response', 'Predicted_Response']
#                 writer = csv.DictWriter(file, fieldnames=fields)
#                 writer.writeheader()  # Writes the header row
                
#             actual_responses = []
#             predicted_responses = []
#             project = project_files[project_key]

#             counter = 0

#             # Load the questions JSON file
#             questions_json_file = project["questions_json_file"]
#             with open(questions_json_file, 'r', encoding='utf-8') as pf:
#                 questions = json.load(pf)
            
#             # Save question[0]["answer"] as a variable
#             for idx in range(0, 60): 
#                 category = questions[idx]["category"]
#                 actual_responses.append(questions[idx]["answer"])

#                 try:
#                     # Load the results JSON file
#                     results_file = f"{project["parent_directory"]}/results/{model}/{category}/{idx+1}.json"

#                     with open(results_file, 'r', encoding='utf-8') as rf:
#                         result = json.load(rf)
#                         predicted_responses.append(result["response"]["answer"])

#                     if (result["response"]["answer"] == questions[idx]["answer"]):
#                         counter += 1
#                 except FileNotFoundError as e:
#                     print(e)
#                     predicted_responses.append("N/A")
#                 with open(f'{model}_{project_key}.csv', 'a', newline='') as file:
#                     writer = csv.writer(file)
#                     # row = {'Model': f'{model}', 'Question': f'{idx+1}', 'Actual_Response': f'{questions[idx]["answer"]}', 'Predicted_Response': f'{result["response"]["answer"]}'}
#                     row = [f'{model}', f'Q{idx+1}', f'{category}', f'{questions[idx]["answer"]}', f'{result["response"]["answer"]}']
#                     writer.writerow(row)
            
#             print(f"Number of total correct responses for {project_key}: {counter}")
#             cm = confusion_matrix(actual_responses, predicted_responses)

#             # Calculate metrics
#             accuracy = accuracy_score(actual_responses, predicted_responses)
#             precision = precision_score(actual_responses, predicted_responses, pos_label = "YES", average="macro")
#             recall = recall_score(actual_responses, predicted_responses, pos_label = "YES", average="macro")
#             f1 = f1_score(actual_responses, predicted_responses, pos_label = "YES", average="macro")

#             print(f'Accuracy: {accuracy}')
#             print(f'Precision: {precision}')
#             print(f'Recall: {recall}')
#             print(f'F1 Score: {f1}')

#             row = ['Accuracy', 'Precision', 'Recall', 'F1 Score']

#             with open(f'{model}_{project_key}.csv', 'a', newline='\n') as file:
#                 writer = csv.writer(file)
#                 writer.writerow(row)
#                 row = [f'{accuracy}', f'{precision}', f'{recall}', f'{f1}']
#                 writer.writerow(row)

#             # print(cm)  

#         # for category in actual_responses.keys():
#         #     cm = confusion_matrix(actual_responses[category], predicted_responses[category])
#         #     print(f"Confusion matrix for category: {category}\n", cm)  

# def write_dry_run_responses_to_csv():
#     models = ["claude-sonnet-4.6", "gemini-3-flash-preview", "gpt-5.4-nano", "llama-3.3-70b-instruct"]

#     for model in models: 
#         print (f"\n--- For model: {model} ---\n")

#         with open("./project_files.json", 'r', encoding='utf-8') as pf:
#             project_files = json.load(pf)

#         for project_key in project_files:
#             # print (f"\n--- For project: {project_key} ---\n")
#             with open(f'{project_files[project_key]["parent_directory"]}/dry_run/csvs/{model}_{project_key}.csv', 'w', newline='') as file:
#                 fields = ['Model', 'Question', 'Category', 'Actual_Response', 'Predicted_Response']
#                 writer = csv.DictWriter(file, fieldnames=fields)
#                 writer.writeheader()  # Writes the header row
                
#             actual_responses = []
#             predicted_responses = []
#             project = project_files[project_key]

#             counter = 0

#             # Load the questions JSON file
#             questions_json_file = project["questions_json_file"]
#             with open(questions_json_file, 'r', encoding='utf-8') as pf:
#                 questions = json.load(pf)
            
#             # Save question[0]["answer"] as a variable
#             for idx in range(0, 60): 
#                 category = questions[idx]["category"]
#                 actual_responses.append(questions[idx]["answer"])

#                 try:
#                     # Load the results JSON file
#                     results_file = f"{project["parent_directory"]}/dry_run/{model}/{category}/{idx+1}.json"

#                     with open(results_file, 'r', encoding='utf-8') as rf:
#                         result = json.load(rf)
#                         predicted_responses.append(result["response"]["answer"])

#                     if (result["response"]["answer"] == questions[idx]["answer"]):
#                         counter += 1
#                 except FileNotFoundError as e:
#                     print(e)
#                     predicted_responses.append("N/A")

#                 with open(f'{project_files[project_key]["parent_directory"]}/dry_run/csvs/{model}_{project_key}.csv', 'a', newline='') as file:
#                     writer = csv.writer(file)
#                     # row = {'Model': f'{model}', 'Question': f'{idx+1}', 'Actual_Response': f'{questions[idx]["answer"]}', 'Predicted_Response': f'{result["response"]["answer"]}'}
#                     row = [f'{model}', f'Q{idx+1}', f'{category}', f'{questions[idx]["answer"]}', f'{predicted_responses[idx]}']
#                     writer.writerow(row)
            
#             print(f"Number of total correct responses for {project_key}: {counter}")
#             cm = confusion_matrix(actual_responses, predicted_responses)

#             # Calculate metrics
#             accuracy = accuracy_score(actual_responses, predicted_responses)
#             precision = precision_score(actual_responses, predicted_responses, pos_label = "YES", average="macro")
#             recall = recall_score(actual_responses, predicted_responses, pos_label = "YES", average="macro")
#             f1 = f1_score(actual_responses, predicted_responses, pos_label = "YES", average="macro")

#             print(f'Accuracy: {accuracy}')
#             print(f'Precision: {precision}')
#             print(f'Recall: {recall}')
#             print(f'F1 Score: {f1}')

#             row = ['Accuracy', 'Precision', 'Recall', 'F1 Score']

#             with open(f'{project["parent_directory"]}/dry_run/csvs/{model}_{project_key}.csv', 'a', newline='\n') as file:
#                 writer = csv.writer(file)
#                 writer.writerow(row)
#                 row = [f'{accuracy}', f'{precision}', f'{recall}', f'{f1}']
#                 writer.writerow(row)

#             # print(cm)  

#         # for category in actual_responses.keys():
#         #     cm = confusion_matrix(actual_responses[category], predicted_responses[category])
#         #     print(f"Confusion matrix for category: {category}\n", cm)  

def write_pnet_and_ncir_responses_to_csv():
    models = ["claude-sonnet-4.6", "gemini-3-flash-preview", "gpt-5.4-nano", "llama-3.3-70b-instruct"]

    # project_files_dict = project_files.meshinger_project({})

    for model in models: 
        print (f"\n--- For model: {model} ---\n")

        with open("./project_files.json", 'r', encoding='utf-8') as pf:
            project_files_dict = json.load(pf)

        for project_key in project_files_dict:
            # print (f"\n--- For project: {project_key} ---\n")
            with open(f'{project_files_dict[project_key]["parent_directory"]}/results/PNet&NCir/{model}_{project_key}.csv', 'w', newline='') as file:
                fields = ['Model', 'Question', 'Category', 'Actual_Response', 'Predicted_Response']
                writer = csv.DictWriter(file, fieldnames=fields)
                writer.writeheader()  # Writes the header row
                
            actual_responses = []
            predicted_responses = []
            project = project_files_dict[project_key]

            counter = 0

            # Load the questions JSON file
            questions_json_file = project["questions_json_file"]
            with open(questions_json_file, 'r', encoding='utf-8') as pf:
                questions = json.load(pf)
            
            # Save question[0]["answer"] as a variable
            for idx in range(0, 15): 
                category = questions[idx]["category"]
                actual_responses.append(questions[idx]["answer"])

                try:
                    # Load the results JSON file
                    results_file = f"{project["parent_directory"]}/results/PNet&NCir/{model}/{category}/{idx+1}.json"

                    with open(results_file, 'r', encoding='utf-8') as rf:
                        result = json.load(rf)
                        predicted_responses.append(result["response"]["answer"])

                    if (result["response"]["answer"] == questions[idx]["answer"]):
                        counter += 1
                except FileNotFoundError as e:
                    # print(e)
                    predicted_responses.append("N/A")

                with open(f'{project_files_dict[project_key]["parent_directory"]}/results/PNet&NCir/{model}_{project_key}.csv', 'a', newline='') as file:
                    writer = csv.writer(file)
                    # row = {'Model': f'{model}', 'Question': f'{idx+1}', 'Actual_Response': f'{questions[idx]["answer"]}', 'Predicted_Response': f'{result["response"]["answer"]}'}
                    row = [f'{model}', f'Q{idx+1}', f'{category}', f'{questions[idx]["answer"]}', f'{predicted_responses[idx]}']
                    writer.writerow(row)
            
            not_app = predicted_responses.count("N/A")
            available = (60 - not_app)
            print(len(actual_responses[:available]))

            # print(f"Got N/A {predicted_responses.count("N/A")} many times")
            print(f"Number of total correct responses for {project_key}: {counter}")
            cm = confusion_matrix(actual_responses[:available], predicted_responses[:available])

            # Calculate metrics
            accuracy = accuracy_score(actual_responses[:available], predicted_responses[:available])
            precision = precision_score(actual_responses[:available], predicted_responses[:available], pos_label = "YES", average="macro")
            recall = recall_score(actual_responses[:available], predicted_responses[:available], pos_label = "YES", average="macro")
            f1 = f1_score(actual_responses[:available], predicted_responses[:available], pos_label = "YES", average="macro")

            print(f'Accuracy: {accuracy}')
            print(f'Precision: {precision}')
            print(f'Recall: {recall}')
            print(f'F1 Score: {f1}')

            row = ['Accuracy', 'Precision', 'Recall', 'F1 Score']

            with open(f'{project["parent_directory"]}/results/PNet&NCir/{model}_{project_key}.csv', 'a', newline='\n') as file:
                writer = csv.writer(file)
                writer.writerow(row)
                row = [f'{accuracy}', f'{precision}', f'{recall}', f'{f1}']
                writer.writerow(row)

            # print(cm)  

        # for category in actual_responses.keys():
        #     cm = confusion_matrix(actual_responses[category], predicted_responses[category])
        #     print(f"Confusion matrix for category: {category}\n", cm)  

# This function basically reads in results from JSON.cir and .net results
def write_nnet_and_pcir_responses_to_csv():
    models = ["claude-sonnet-4.6", "gemini-3-flash-preview", "gpt-5.4-nano", "llama-3.3-70b-instruct"]

    for model in models: 
        print (f"\n--- For model: {model} ---\n")

        with open("./project_files.json", 'r', encoding='utf-8') as pf:
            project_files = json.load(pf)

        for project_key in project_files:
            # print (f"\n--- For project: {project_key} ---\n")
            with open(f'{project_files[project_key]["parent_directory"]}/results/NNet&PCir/{model}_{project_key}.csv', 'w', newline='') as file:
                fields = ['Model', 'Question', 'Category', 'Actual_Response', 'Predicted_Response']
                writer = csv.DictWriter(file, fieldnames=fields)
                writer.writeheader()  # Writes the header row
                
            actual_responses = []
            predicted_responses = []
            project = project_files[project_key]

            counter = 0

            # Load the questions JSON file
            questions_json_file = project["questions_json_file"]
            with open(questions_json_file, 'r', encoding='utf-8') as pf:
                questions = json.load(pf)
            
            # Save question[0]["answer"] as a variable
            for idx in range(0, 15): 
                category = questions[idx]["category"]
                actual_responses.append(questions[idx]["answer"])

                try:
                    # Load the results JSON file
                    results_file = f"{project["parent_directory"]}/results/NNet&PCir/{model}/{category}/{idx+1}.json"

                    with open(results_file, 'r', encoding='utf-8') as rf:
                        result = json.load(rf)
                        predicted_responses.append(result["response"]["answer"])

                    if (result["response"]["answer"] == questions[idx]["answer"]):
                        counter += 1
                except FileNotFoundError as e:
                    print(e)
                    predicted_responses.append("N/A")
                with open(f'{project_files[project_key]["parent_directory"]}/results/NNet&PCir/{model}_{project_key}.csv', 'a', newline='') as file:
                    writer = csv.writer(file)
                    row = [f'{model}', f'Q{idx+1}', f'{category}', f'{questions[idx]["answer"]}', f'{result["response"]["answer"]}']
                    writer.writerow(row)
            
            not_app = predicted_responses.count("N/A")
            available = (60 - not_app)
            print(len(actual_responses[:available]))

            # print(f"Got N/A {predicted_responses.count("N/A")} many times")
            print(f"Number of total correct responses for {project_key}: {counter}")
            cm = confusion_matrix(actual_responses[:available], predicted_responses[:available])

            # Calculate metrics
            accuracy = accuracy_score(actual_responses[:available], predicted_responses[:available])
            precision = precision_score(actual_responses[:available], predicted_responses[:available], pos_label = "YES", average="macro")
            recall = recall_score(actual_responses[:available], predicted_responses[:available], pos_label = "YES", average="macro")
            f1 = f1_score(actual_responses[:available], predicted_responses[:available], pos_label = "YES", average="macro")

            print(f'Accuracy: {accuracy}')
            print(f'Precision: {precision}')
            print(f'Recall: {recall}')
            print(f'F1 Score: {f1}')

            row = ['Accuracy', 'Precision', 'Recall', 'F1 Score']

            with open(f'{project["parent_directory"]}/results/NNet&PCir/{model}_{project_key}.csv', 'a', newline='\n') as file:
                writer = csv.writer(file)
                writer.writerow(row)
                row = [f'{accuracy}', f'{precision}', f'{recall}', f'{f1}']
                writer.writerow(row)

def write_schematic_as_pdfs_responses_to_csv():
    model = "gpt-5.4-nano"

    print (f"\n--- For model: {model} ---\n")

    with open("./project_files.json", 'r', encoding='utf-8') as pf:
        project_files = json.load(pf)

    for project_key in project_files:
        # print (f"\n--- For project: {project_key} ---\n")
        with open(f'{project_files[project_key]["parent_directory"]}/results/schematic_as_pdf/{model}_{project_key}.csv', 'w', newline='') as file:
            fields = ['Model', 'Question', 'Category', 'Actual_Response', 'Predicted_Response']
            writer = csv.DictWriter(file, fieldnames=fields)
            writer.writeheader()  # Writes the header row
            
        actual_responses = []
        predicted_responses = []
        project = project_files[project_key]

        counter = 0

        # Load the questions JSON file
        questions_json_file = project["questions_json_file"]
        with open(questions_json_file, 'r', encoding='utf-8') as pf:
            questions = json.load(pf)
        
        # Save question[0]["answer"] as a variable
        for idx in range(0, 15): 
            category = questions[idx]["category"]
            actual_responses.append(questions[idx]["answer"])

            try:
                # Load the results JSON file
                results_file = f"{project["parent_directory"]}/results/schematic_as_pdf/{model}/{category}/{idx+1}.json"

                with open(results_file, 'r', encoding='utf-8') as rf:
                    result = json.load(rf)
                    predicted_responses.append(result["response"]["answer"])

                if (result["response"]["answer"] == questions[idx]["answer"]):
                    counter += 1
            except FileNotFoundError as e:
                print(e)
                predicted_responses.append("N/A")
            with open(f'{project_files[project_key]["parent_directory"]}/results/schematic_as_pdf/{model}_{project_key}.csv', 'a', newline='') as file:
                writer = csv.writer(file)
                row = [f'{model}', f'Q{idx+1}', f'{category}', f'{questions[idx]["answer"]}', f'{result["response"]["answer"]}']
                writer.writerow(row)
        
        not_app = predicted_responses.count("N/A")
        available = (60 - not_app)
        print(len(actual_responses[:available]))

        # print(f"Got N/A {predicted_responses.count("N/A")} many times")
        print(f"Number of total correct responses for {project_key}: {counter}")
        cm = confusion_matrix(actual_responses[:available], predicted_responses[:available])

        # Calculate metrics
        accuracy = accuracy_score(actual_responses[:available], predicted_responses[:available])
        precision = precision_score(actual_responses[:available], predicted_responses[:available], pos_label = "YES", average="macro")
        recall = recall_score(actual_responses[:available], predicted_responses[:available], pos_label = "YES", average="macro")
        f1 = f1_score(actual_responses[:available], predicted_responses[:available], pos_label = "YES", average="macro")

        print(f'Accuracy: {accuracy}')
        print(f'Precision: {precision}')
        print(f'Recall: {recall}')
        print(f'F1 Score: {f1}')

        row = ['Accuracy', 'Precision', 'Recall', 'F1 Score']

        with open(f'{project["parent_directory"]}/results/schematic_as_pdf/{model}_{project_key}.csv', 'a', newline='\n') as file:
            writer = csv.writer(file)
            writer.writerow(row)
            row = [f'{accuracy}', f'{precision}', f'{recall}', f'{f1}']
            writer.writerow(row)


if __name__ == "__main__":
    # write_spice_json_and_circuit_contents_responses_to_csv()
    write_pnet_and_ncir_responses_to_csv()