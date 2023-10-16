import azure.functions as func
import logging
import datetime
import html
import json
import os
import sys
import re
from io import BytesIO
from azure.storage.blob import BlobClient, BlobSasPermissions, generate_blob_sas
from azure.storage.blob import BlobServiceClient
#from azure.identity import DefaultAzureCredential
from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.core.credentials import AzureKeyCredential
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import *
from azure.search.documents import SearchClient

MAX_SECTION_LENGTH = 1000
SENTENCE_SEARCH_LIMIT = 100
SECTION_OVERLAP = 100
form_recognizer_key = ""
form_recognizer_name = ""
search_service_host = ""
search_service_key =  ""
index_name =  ""

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)
@app.function_name(name="DocumentIndexer")

#this sample is a modified version of the prepdocs script found at https://github.com/Azure-Samples/azure-search-openai-demo - which was desigend to run on a PC/server. I have modified to be an Azure Function
#this function accepts a JSON body which contains configuration information how to process the referenced document
#it will fetch the file from Azure Blob storage, and then process it
#in theory it could process several files, but for now only accespts one file at a time
#this overcomes problem of the other function below wich can onlu accept small files. In theory this function could prcess larger files
#it then chunks the document into sections, and adds to Azure Search index
#it assumes Azure Forms recogniser name and key are added as config params for the function
#search svc name and key can either be passed as params, or if not are fetched frm config params for function
#it assumes key and names for blob container are sent in JSON body
#this is provided as a sample only. It has not been tested thoroughly, and might not adhere to best pratice design / architecture

#note on authentication to Azure Blobs / Container
# The recommendation is to use AzureCredential to authenticate, and not handle keys/connection string. In this way you rather use managed identity and grant access to this identity to the 
# blob container in question. This is what is recommended for production. However, for this demo, I am passing into the Azure Function the key and params for the container. This is not what
# should be done, this is not good practice. The idea was that the function is re-usable and can handle any blob account/contaoner/blob
# If you going to pass in a key, rather pass in a keyname to an Azure Key Vault key, and have the function get the actualy key from the keyvault, using a managed identity
# this is documented here - https://learn.microsoft.com/en-us/azure/storage/blobs/storage-quickstart-blobs-python
@app.route(route="FetchandIndexDocument",methods=[func.HttpMethod.POST])
def FetchandIndexDocument(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('FetchandIndexDocument function started.')

    req_body = None

    # get JSON body
    try:
        req_body = req.get_json()
    except ValueError:
        pass

    # exit function if params don't exist
    if req_body is None:
        json_response = {"status":"failure","error":"Must post JSON body found with config params for function to execute"}

        #return failure and error message
        return func.HttpResponse(    
            json.dumps(json_response),
            mimetype="application/json",
            status_code=200
        )
    logging.info('Got JSON body')
    try:

        #from settings.json/app settings
        InitGlobalVariables()
   
        
        #from JSON
        blob_name = req_body["blobName"]
        file_source_type = req_body["fileSourceType"]
        friendly_file_url =  req_body["friendlyFileUrl"]
        blob_account_name =  req_body["blobAccountName"]
        blob_account_key =  req_body["blobAccountKey"]
        blob_container = req_body["blobContainer"]
        
        global MAX_SECTION_LENGTH
        MAX_SECTION_LENGTH =  req_body["chunkSectionSize"]
        content_extractor =  req_body["contentExtractor"] #not used at this point, in the future could change to use localPDF parser instead
        #global search_service_host
        global search_service_host
        search_service_host =  req_body["searchServiceHost"]
        global search_service_key
        search_service_key =  req_body["searchServiceKey"]
        global index_name
        index_name =  req_body["indexName"]
        logging.info('Got required environment settings.')


        #for local Azurite storage = "DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;BlobEndpoint=https://127.0.0.1:10000/devstoreaccount1"
        azure_blob_cn_string = f"DefaultEndpointsProtocol=https;AccountName={blob_account_name};AccountKey={blob_account_key};EndpointSuffix=core.windows.net"
                
        #credential = DefaultAzureCredential() - prefered method to authenticate instead of connection string
        
        # Initialize the BlobServiceClient using the connection string
        blob_service_client = BlobServiceClient.from_connection_string(azure_blob_cn_string)

        # Get a reference to the container
        #container_client = blob_service_client.get_container_client(blob_container)

        # Loop through each blob in a container       
        #blob_list = container_client.list_blobs()
        #count_blobs = 0
        #for blob in blob_list:
        #    if blob.name.lower().endswith(".pdf"):  
         
        logging.info('processing image blob : ' + blob_name)
        #blob_service_client.get_blob_client(container=container_name, blob="sample-blob.txt")
        blob_client = blob_service_client.get_blob_client(container=blob_container, blob=blob_name)
        # download blob image into a stream
        file_stream = BytesIO()
        blob_client.download_blob().readinto(file_stream)
        #set index back to 0 i.e. begining of file
        file_stream.seek(0)
        #generate a map of the document
        page_map = get_document_text(blob_name.lower(),fileblob = file_stream)
        #create sections from map
        sections = create_sections(blob_name.lower(), friendly_file_url,page_map)
        #add each section into index as an item
        count_chunks = index_sections(blob_name.lower(), sections)
        #respond
        json_response = {"status":"success","indexName":index_name,"chunksIndexed":count_chunks}

        #return success and new file name
        return func.HttpResponse(    
            json.dumps(json_response),
            mimetype="application/json",
            status_code=200
        )

    except KeyError as e:    
         json_response = {"status":"failure","error": "Cannot find key in dictionary - " + str(e)}
         return func.HttpResponse(json.dumps(json_response),mimetype="application/json",status_code=200)
    except Exception as e:
        if hasattr(e, 'message'):
            json_response = {"status":"failure","error": e.message}
        else:
            json_response = {"status":"failure","error": str(e)}
        
        #return error and new file name
        return func.HttpResponse(json.dumps(json_response),mimetype="application/json",status_code=200)    


#this function accepts a binary body which is the document, along with querystring params such as name, url, chunksize etc
#it then chunks the document into sections, and adds to Azure Search index
#it assumes Azure Forms recogniser name and key are added as config params for the function
#search svc name and key can either be passed as params, or if not are fetched frm config params for function
#this only works for PDF documents and only if PDF document is under around 10mb
#this is provided as a sample only. It has not been tested thoroughly, and might not adhere to best pratice design / architecture
@app.route(route="IndexDocument",methods=[func.HttpMethod.POST])
def IndexDocument(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('IndexDocument function started.')

     #from settings.json/app settings
    InitGlobalVariables()

    #required params
    file_name = req.params.get('filename')
    file_friendly_url = req.params.get('url')
    global index_name
    index_name = req.params.get('index')

    #optional params
    chunk_size = req.params.get('chunksize')
    if chunk_size:
        global MAX_SECTION_LENGTH
        MAX_SECTION_LENGTH = int(chunk_size)
    
    global search_service_host
    search_svc_name = req.params.get('srchsvc')
    if search_svc_name:        
        search_service_host = search_svc_name
    else:
        search_service_host = os.environ['search_svc_name']

    global search_service_key
    search_svc_key = req.params.get('srchkey')
    if search_svc_key:        
        search_service_key = search_svc_key
    else:
        search_service_key = os.environ['search_svc_key']

    req_body_bytes = req.get_body()

    if not file_name or not index_name or not file_friendly_url or len(req_body_bytes)==0:
        logging.info('Missing required querystring param, filename, url and index are required OR not binary file posted in body')
        json_response = {"status":"failure","error": "filename, url and index are required querystring params. srchsvc, srchkey and chunksize are optional. Ensure binary file posted in body"}
        return func.HttpResponse(json.dumps(json_response),mimetype="application/json",status_code=200)
    else:
        try:
            
            logging.info(f'Create page map for file: {file_name.lower()}')
            page_map = get_document_text(file_name.lower(),fileblob = req_body_bytes)
            logging.info(f'Create sections for file: {file_name.lower()}')
            sections = create_sections(file_name.lower(),file_friendly_url,page_map)   
            logging.info(f'Indexing sections for file: {file_name.lower()}')
            count_chunks = index_sections(file_name.lower(), sections)
            logging.info(f'Indexing done or file: {file_name.lower()}, indexName:{index_name},chunksIndexed:{count_chunks}')
            json_response = {"status":"success","indexName":index_name,"chunksIndexed":count_chunks,"fileName":file_name}

            #return success and new file name
            return func.HttpResponse(    
                json.dumps(json_response),
                mimetype="application/json",
                status_code=200
            )
        
            #if file was passed in using multpart form this code below will get access to the form file
            #for input_file in req.files.values():
            #filename = input_file.filename
        except KeyError as e:    
         json_response = {"status":"failure","error": "Cannot find key in dictionary - " + str(e)}
         return func.HttpResponse(json.dumps(json_response),mimetype="application/json",status_code=200)
        except Exception as e:
            if hasattr(e, 'message'):
                json_response = {"status":"failure","error": e.message}
            else:
                json_response = {"status":"failure","error": str(e)}
        
        #return error and new file name
        return func.HttpResponse(json.dumps(json_response),mimetype="application/json",status_code=200)   

def test():
    print(search_service_host) 
    
def InitGlobalVariables():
    global form_recognizer_name
    form_recognizer_name= os.environ['form_recognizer_service_name']
    global form_recognizer_key
    form_recognizer_key = os.environ['form_recognizer_service_key']


def table_to_html(table):
    table_html = "<table>"
    rows = [sorted([cell for cell in table.cells if cell.row_index == i], key=lambda cell: cell.column_index) for i in range(table.row_count)]
    for row_cells in rows:
        table_html += "<tr>"
        for cell in row_cells:
            tag = "th" if (cell.kind == "columnHeader" or cell.kind == "rowHeader") else "td"
            cell_spans = ""
            if cell.column_span > 1: cell_spans += f" colSpan={cell.column_span}"
            if cell.row_span > 1: cell_spans += f" rowSpan={cell.row_span}"
            table_html += f"<{tag}{cell_spans}>{html.escape(cell.content)}</{tag}>"
        table_html +="</tr>"
    table_html += "</table>"
    return table_html

def split_text(page_map,filename):
    SENTENCE_ENDINGS = [".", "!", "?"]
    WORDS_BREAKS = [",", ";", ":", " ", "(", ")", "[", "]", "{", "}", "\t", "\n"]
    logging.info(f"Splitting '{filename}' into sections")

    def find_page(offset):
        l = len(page_map)
        for i in range(l - 1):
            if offset >= page_map[i][1] and offset < page_map[i + 1][1]:
                return i
        return l - 1

    all_text = "".join(p[2] for p in page_map)
    length = len(all_text)
    start = 0
    end = length
    while start + SECTION_OVERLAP < length:
        last_word = -1
        end = start + MAX_SECTION_LENGTH

        if end > length:
            end = length
        else:
            # Try to find the end of the sentence
            while end < length and (end - start - MAX_SECTION_LENGTH) < SENTENCE_SEARCH_LIMIT and all_text[end] not in SENTENCE_ENDINGS:
                if all_text[end] in WORDS_BREAKS:
                    last_word = end
                end += 1
            if end < length and all_text[end] not in SENTENCE_ENDINGS and last_word > 0:
                end = last_word # Fall back to at least keeping a whole word
        if end < length:
            end += 1

        # Try to find the start of the sentence or at least a whole word boundary
        last_word = -1
        while start > 0 and start > end - MAX_SECTION_LENGTH - 2 * SENTENCE_SEARCH_LIMIT and all_text[start] not in SENTENCE_ENDINGS:
            if all_text[start] in WORDS_BREAKS:
                last_word = start
            start -= 1
        if all_text[start] not in SENTENCE_ENDINGS and last_word > 0:
            start = last_word
        if start > 0:
            start += 1

        section_text = all_text[start:end]
        yield (section_text, find_page(start))

        last_table_start = section_text.rfind("<table")
        if (last_table_start > 2 * SENTENCE_SEARCH_LIMIT and last_table_start > section_text.rfind("</table")):
            # If the section ends with an unclosed table, we need to start the next section with the table.
            # If table starts inside SENTENCE_SEARCH_LIMIT, we ignore it, as that will cause an infinite loop for tables longer than MAX_SECTION_LENGTH
            # If last table starts inside SECTION_OVERLAP, keep overlapping
            logging.info(f"Section ends with unclosed table, starting next section with the table at page {find_page(start)} offset {start} table start {last_table_start}")
            start = min(end - SECTION_OVERLAP, start + last_table_start)
        else:
            start = end - SECTION_OVERLAP
        
    if start + SECTION_OVERLAP < end:
        yield (all_text[start:end], find_page(start))

def create_sections(filename,url, page_map):
    for i, (section, pagenum) in enumerate(split_text(page_map,filename)):
        yield {
            "id": re.sub("[^0-9a-zA-Z_-]","_",f"{filename}-{i}"),
            "content": section,
            "title": f"{os.path.basename(filename)} [page {pagenum}]",
            "filepath": os.path.basename(filename),
            "url": url,
            "chunk_id":str(i)
        }

 

def get_document_text(filename,fileblob):
    offset = 0
    page_map = []
    logging.info(f"Extracting text from '{filename}' using Azure Form Recognizer")

    form_recognizer_client = DocumentAnalysisClient(endpoint=f"https://{form_recognizer_name}.cognitiveservices.azure.com/", credential=AzureKeyCredential(form_recognizer_key), headers={"x-ms-useragent": "azure-search-chat-demo/1.0.0"})
    #with open(filename, "rb") as f:
    #fileblob.seek(0)
    poller = form_recognizer_client.begin_analyze_document("prebuilt-layout", document = fileblob)
    form_recognizer_results = poller.result()
    
    for page_num, page in enumerate(form_recognizer_results.pages):
        tables_on_page = [table for table in form_recognizer_results.tables if table.bounding_regions[0].page_number == page_num + 1]

        # mark all positions of the table spans in the page
        page_offset = page.spans[0].offset
        page_length = page.spans[0].length
        table_chars = [-1]*page_length
        for table_id, table in enumerate(tables_on_page):
            for span in table.spans:
               # replace all table spans with "table_id" in table_chars array
                for i in range(span.length):
                    idx = span.offset - page_offset + i
                    if idx >=0 and idx < page_length:
                        table_chars[idx] = table_id

        # build page text by replacing charcters in table spans with table html
        page_text = ""
        added_tables = set()
        for idx, table_id in enumerate(table_chars):
            if table_id == -1:
                page_text += form_recognizer_results.content[page_offset + idx]
            elif not table_id in added_tables:
                page_text += table_to_html(tables_on_page[table_id])
                added_tables.add(table_id)

        page_text += " "
        page_map.append((page_num, offset, page_text))
        offset += len(page_text)

    return page_map

def index_sections(filename, sections):
    logging.info(f"Indexing sections from '{filename}' into search index ")
    search_client = SearchClient(endpoint=f"https://{search_service_host}.search.windows.net/",
                                    index_name=index_name,
                                    credential=AzureKeyCredential(search_service_key))
    i = 0
    batch = []
    for s in sections:
        batch.append(s)
        i += 1
        if i % 1000 == 0:
            results = search_client.upload_documents(documents=batch)
            succeeded = sum([1 for r in results if r.succeeded])
            logging.info(f"\tIndexed {len(results)} sections, {succeeded} succeeded")
            batch = []

    if len(batch) > 0:
        results = search_client.upload_documents(documents=batch)
        succeeded = sum([1 for r in results if r.succeeded])
        logging.info(f"\tIndexed {len(results)} sections, {succeeded} succeeded")

    return i
