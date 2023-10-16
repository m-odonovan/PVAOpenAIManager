## Readme
This must be installed before the GenericPVAGPTManager solution. Both a managed and unmanaged version of the connector is available.

It is a Power Plaform custom connector which "wraps" the Azure Function for indexing of a document. It is used in the GenericPVAGPTManager solution by a custom page titled "Index Document"

Once imported, edit the Environment Variable called "ABC" and set to the Azure Function Hostname e.g. hostname.azurewebsites.net. For managed solution, edit this variable value in the default solution. For unmanaged solution, edit this variable directly in the DocumentIndexerConnector solution.


