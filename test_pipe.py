import yaml

with open(r'task_subtask.yml') as file:
    # The FullLoader parameter handles the conversion from YAML
    # scalar values to Python the dictionary format
    list_of_task_and_subtasks= yaml.load(file, Loader=yaml.FullLoader)




list_of_task = list(list_of_task_and_subtasks.keys())

print(list_of_task)