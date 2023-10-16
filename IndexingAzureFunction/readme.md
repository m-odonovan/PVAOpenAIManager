## Azure Function
Here you will find the indexing Azure Function. You will need to create an Azure Function and import yourself.

## Configuration Notes
This Python function was created based on a script sample at https://github.com/Azure-Samples/azure-search-openai-demo. It has been modified from a command line script to an Azure Function. It is built using the V2 Python Azure Function model, as documented here - https://learn.microsoft.com/en-us/azure/azure-functions/create-first-function-vs-code-python.

1. You will need to create an Azure Function App as type Python 3.11, and deploy the attached function to it
2. Rename local.example.settings to local.settings. This configuration file is used for local PC development. You should use the application settings in Azure Function for live configuration. You will need to add the Azure Forms keys and optional the Azure Search keys.
3. The Azure Forms Recognizer config params are required. This allows the Azure Function to use Forms Recogniser to open a PDF file and exctract its contents. The search service keys are optional, as these can be passed into this function by the caller.
4. The DocumentIndexerConnector calls this Azure Function, specifically only the IndexDocument function within this function.
5. You must copy the hostname of your Azure Function and configure the environment variable for the connector to point to the Azure Function hostname e.g. host.azurewebsites.net. You will also need to copy the function key, and paste this value into Power platform connection. This is how the Power Platform will authenticate to this function.

## Important
Read the comments in the Azure Function app.py file to understand how this Azure Function works. It also has important notes to consider.
