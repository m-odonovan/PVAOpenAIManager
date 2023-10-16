# PVAOpenAIManager
Sample solution which allows you to manage and configure Azure Open AI GPT powered prompts for Power Virtual Agent via a Model Driven Power App

## Background
This is provided as a solution accelerator. It's a sample solution which is not supported by Microsoft or myself. Use as a starter to help you get going quickly or simply as a learning tool. 

It was created as a result of me having to create Azure Open AI Powered Virtual Agent demo's and PoC solutions regularly, and having to re-create the Power Automate Flow + Prompts each time. This allows me to create these now far quicker, by simply defining new "skills/topcs" in a Model Driven Power App.

## Features
Here is a list of core features of the solution

- Create 3 types of Azure Open AI powered prompts scenarios:
  1. Ask questions of content (indexed by Azure Search). Supports multi-turn conversations, and several options for Azure Search e.g semantic vs keyword etc. As well as "manual" Azure Search query vs Azure Open AI extensions for Azure Search
  2. Pure prompt driven conversation. i.e. no data/content behind conversation.
  3. Ask questions of SQL Server data. Supports dynamics generation of SQL Select statement, execution of statement, and answering initial user question using the data.
- Manage these prompts in a Model Driven app, as well as:
  1. Define Azure Search Endpoints to be used for content based prompts
  2.  Define Azure Open AI Endpoints to be used in various prompts
  3. Test Azure Search queries (you content based conversations are only as good as search results)
  4. Add content (PDF documents) into your Azure Search index, and choose config options such as chunk overlap size. Source file location supports Azure Blob storage, in future SharePoint libraries

## How it works
There are 6 main components to this solution
1. Admin Model Driven App (PVA GPT Manager)
2. Power Virtual Agent Chat Bot (Chetty)
3. Several Power Automate Flows, which are used by the PVA chat bot to fetch prompt and endpoints from Dataverse and query/call Azure Search, SQL Server, Azure Open AI and more
4. Several Power Automate Flows, which allow the Admin Model Driven app to query search index
5. Azure Function, which chunks PDF documents and adds to Azure Search Index. Azure Function is written in Python
6. Custom Power Platform connector, for the Azure Function.

Watch the following YouTube recording to understand how this all works and fits together - <TBC>

## Provided "As-Is"
This is a a starter / sample. It hasn't been well tested, and is missing some key features that I hope to add over time. It not officialy supported by myself or Microsoft. However, because the unmanaged and managed solution is provided, you should be able to support it yourself, either directly or through a certified Microsoft partner.
