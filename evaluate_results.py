import csv

import project_files

import json
from sklearn.metrics import confusion_matrix, accuracy_score, precision_score, recall_score, f1_score

class EvaluateResults:
    def __init__(self):
        self.llm_models = ["claude-sonnet-4.6", "gemini-3-flash-preview", "gpt-5.4-nano", "llama-3.3-70b-instruct"]
        self.actual_responses = []
        self.predicted_responses = []

        with open("project_files.json", 'r', encoding='utf-8') as pf:
            self.project_files_dict = json.load(pf)

    def _create_header_csv_for_model_with_mode(self, output_file: str, model: str, mode: str):
        with open(output_file, 'w', newline='') as file:
            fields = ['Model', 'Question', 'Category', 'Actual_Response', 'Predicted_Response']
            writer = csv.DictWriter(file, fieldnames=fields)
            writer.writeheader()  # Writes the header row

    def _evaluate_n_responses_for_mode(self, num_questions: int, mode: str, models: list = None):
        if models is None:
            models = self.llm_models

        for model in models: 

            print (f"\n--- For model: {model} ---\n")

            for project_key in self.project_files_dict:
                self.actual_responses = []
                self.predicted_responses = []

                project = self.project_files_dict[project_key]

                target_csv = f'{project["parent_directory"]}/results/{mode}/{model}_{project_key}.csv'
                self._create_header_csv_for_model_with_mode(target_csv, model, mode)

                # Load the questions JSON file
                questions = self._load_questions_from_file(project["questions_json_file"])
                
                # Save question[0]["answer"] as a variable
                for idx in range(0, num_questions): 
                    category = questions[idx]["category"]
                    self.actual_responses.append(questions[idx]["answer"])

                    # Load the results JSON file
                    results_file = f"{project["parent_directory"]}/results/{mode}/{model}/{category}/{idx+1}.json"
                    self._read_response_from_file(results_file)

                    row = [f'{model}', f'Q{idx+1}', f'{category}', f'{questions[idx]["answer"]}', f'{self.predicted_responses[idx]}']
                    self._write_row_to_csv(target_csv, row)

                cm = confusion_matrix(self.actual_responses[:num_questions], self.predicted_responses[:num_questions])

                # Calculate metrics
                accuracy = accuracy_score(self.actual_responses[:num_questions], self.predicted_responses[:num_questions])
                precision = precision_score(self.actual_responses[:num_questions], self.predicted_responses[:num_questions], pos_label = "YES", average="macro")
                recall = recall_score(self.actual_responses[:num_questions], self.predicted_responses[:num_questions], pos_label = "YES", average="macro")
                f1 = f1_score(self.actual_responses[:num_questions], self.predicted_responses[:num_questions], pos_label = "YES", average="macro")

                print(f'Accuracy: {accuracy}')
                print(f'Precision: {precision}')
                print(f'Recall: {recall}')
                print(f'F1 Score: {f1}')

                self._write_row_to_csv(target_csv, ['Accuracy', 'Precision', 'Recall', 'F1 Score'])
                row = [f'{accuracy}', f'{precision}', f'{recall}', f'{f1}']
                self._write_row_to_csv(target_csv, row)

    def _load_questions_from_file(self, questions_file_path: str) -> dict: 
        with open(questions_file_path, 'r', encoding='utf-8') as qf:
            return json.load(qf)
        return {}

    def _read_response_from_file(self, results_file: str):
        try:
            with open(results_file, 'r', encoding='utf-8') as rf:
                result = json.load(rf)
                self.predicted_responses.append(result["response"]["answer"])

        except FileNotFoundError as e:
            print(e)
            self.predicted_responses.append("N/A")

    def _write_row_to_csv(self, csv_file: str, row: list):
        with open(csv_file, 'a', newline='\n') as file:
            writer = csv.writer(file)
            writer.writerow(row)

    def write_nnet_and_ncir_responses_to_csv(self, num_questions: int = 60, mode: str = "NNet&NCir", models: list = None):
        """
        This function writes responses from 'results/NNet&NCir' for each model into CSV.  
        """
        if models is None:
            models = self.llm_models

        self._evaluate_n_responses_for_mode(num_questions, mode, models)

    def write_nnet_and_pcir_responses_to_csv(self, num_questions: int = 15, mode: str = "NNet&PCir", models: list = None):
        """
        This function writes responses from 'results/NNet&PCir' for each model into CSV.  
        """
        if models is None:
            models = self.llm_models

        self._evaluate_n_responses_for_mode(num_questions, mode, models)

    def write_pnet_and_ncir_responses_to_csv(self, num_questions: int = 15, mode: str = "PNet&NCir", models: list = None):
        """
        This function writes responses from 'results/PNet&NCir' for each model into CSV.  
        """     
        if models is None:
            models = self.llm_models   

        self._evaluate_n_responses_for_mode(num_questions, mode, models)

    def write_pnet_and_pcir_responses_to_csv(self, num_questions: int = 60, mode: str = "PNet&PCir", models: list = None):
        """
        This function writes responses from 'results/PNet&PCir' for each model into CSV.  
        """     
        if models is None:
            models = self.llm_models  

        self._evaluate_n_responses_for_mode(num_questions, mode, models)

    def write_schematic_as_pdfs_responses_to_csv(self, num_questions: int = 15, mode: str = "PDF", models: list = ["gpt-5.4-nano"]):
        """
        This function writes responses from 'results/PDF' for each model into CSV.  
        """   

        self._evaluate_n_responses_for_mode(num_questions, mode, models)

if __name__ == "__main__":
    evaluate_results = EvaluateResults()

    evaluate_results.write_nnet_and_ncir_responses_to_csv()
    evaluate_results.write_nnet_and_pcir_responses_to_csv()
    evaluate_results.write_pnet_and_ncir_responses_to_csv()
    evaluate_results.write_pnet_and_pcir_responses_to_csv()
    evaluate_results.write_schematic_as_pdfs_responses_to_csv()