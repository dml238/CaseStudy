import json
import requests
import sys
import os
import shutil
import csv
import time
import logging
from datetime import datetime
from settings import domain_name, username, password, version, directory

def createValues(fileName, subType):
	#This function creates the specific values string we will need to upload a document via Vault API by setting the neccessary metadata 
	#for the document. 
	try:
		#Since all filenames will be in a standard format, we can parse the various pieces of metadata.
		approved_date_str = fileName[(len(fileName)-24):(len(fileName)-16)]
		approved_date = datetime.strptime(approved_date_str, '%Y%m%d')
		external_ref = fileName[(len(fileName)-11):(len(fileName)-5)]
		trimName = fileName[3:(len(fileName)-25)]
		friendlyName = trimName.replace('_',' ')
		
		postValues ={"name__v":friendlyName,\
				"status__v":"Draft",\
				"lifecycle__v": "Draft to Effective Lifecycle",\
				'subtype__v': subType,\
				"type__v": "Governance and Procedure",\
				"country__v":"unitedStates",\
				"training_impact__c":"false",\
				"owning_department__v":["00D000000000201"],\
				"owning_facility__v": ["00F000000000101"],\
				"previous_document_number__c": external_ref,\
				"ex_approve_date__c":approved_date.date()}
		
		return postValues

	except Exception as ex: #on exception still want to keep going, just log the error and move on. May occur if someone didn't follow the exact naming convention
		f_out.write(fileName + '| ' + str(ex) + '\n')
		error_values = ''
		return error_values

def main():
	global f_out
	
	basepath = os.path.split(os.path.realpath(__file__))[0]
	logfile = os.path.join(basepath,'debug.log')
	logging.basicConfig(filename=logfile,level=logging.DEBUG)
	
	##Create the log output for the script
	today = datetime.today()
	dateAppend = today.strftime('%Y_%m_%d_%H_%M_%S')
	outFileName = "Output_{0}.log".format(dateAppend)
	outFilePath = os.path.join(basepath, outFileName)
	f_out= open(outFilePath,"w+")
	f_out.write('Stage/File|Message \n')
	
	#Create archived folder if doesn't exist
	archiveFolderName = 'Archived'
	archivePath = os.path.join(basepath, archiveFolderName)
	
	if not os.path.exists(archivePath):
		os.mkdir(archivePath)

	#Configs
	headerConfig = {"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"}
	authBaseURL = 'https://' + domain_name + '/api/' + version + '/auth'
	docsURL = 'https://' + domain_name +'/api/' + version + '/objects/documents'
	authData = 'username=' + username + '&password=' + password 
	
	#authenticate 
	authResponse = requests.post(authBaseURL, headers=headerConfig, data=authData)
	authResponseStatusCode = authResponse.status_code
	authResponseContent = json.loads(authResponse.content.decode('utf-8'))
	authResponseStatus = authResponseContent['responseStatus']
		
	if authResponseStatus == 'SUCCESS':
	  sessionId = authResponseContent['sessionId']
	  #New Header with Session Key for file requests from Vault
	  fileRequestHeaders = {"Authorization": sessionId}
	else:
	   f_out.write('Authentication Error|Failed to authenticate with username and password. Error code:' + {authResponseStatusCode} + '\n')
	   sys.exit()

	#With SessionID now able to import documents and set metadata tags.
	#grab list of files to be uploaded
	files = os.listdir(directory)
	
	if len(files) == 1 and files[0] == '.DS_Store':
		f_out.write(directory + ' is currently empty. Exiting \n')
		f_out.close()
		shutil.move(outFilePath,archivePath)
		sys.exit()

	for f in files:
		#documents object settings
		upDocPath = directory + '/' + f
		currentFile = open(upDocPath, 'rb')
		docUpData = {'file' : currentFile}
		
		#Set specific metadata values based on document naming convention
		subTypeCode = f[0:2]
		
		if f[0] == '.': #entered for POC to avoid inadvertantly adding any hidden files within folders.
			continue
		if subTypeCode == 'WI':
			values = createValues(f, 'Work Instruction')
		elif subTypeCode == 'DR': #Directive
			values = createValues(f, 'Directive')
		elif subTypeCode == 'SP': #Standard Operating Procedure
			values = createValues(f, 'Standard Operating Procedure (SOP)')
		elif subTypeCode == 'FM': #Form
			values = createValues(f, 'Form')
		elif subTypeCode == 'GU': #Guidance
			values = createValues(f, 'Guidance')
		elif subTypeCode == 'PL': #Policy
			values = createValues(f, 'Policy')
		elif subTypeCode == 'QM': #Quality Management
			values = createValues(f, 'Quality Manual')
		else: #handle the case if someone uploaded a file but does not conform to designated standard. Save the API call. 
			f_out.write(f + '|' + 'File was not uploaded, filename did not conform to designated standard. \n')
			currentFile.close()
			continue
		
		#let's upload the files via Vault API
		if values != '':
			docUpResponse = requests.post(docsURL, headers=fileRequestHeaders, files=docUpData, data=values)
			docUpResponseContent = json.loads(docUpResponse.content.decode('utf-8'))
			docUpResponseStatus = docUpResponseContent['responseStatus']
			
			if docUpResponseStatus == 'SUCCESS':
				f_out.write(f + '|' + json.dumps(docUpResponseContent)+'\n')
				docID = docUpResponseContent['id']
				docIDs.append(docID) #creating this array for future expansion if we want to return these id's for future automation. 
			else:
				
				f_out.write(f + '|' + json.dumps(docUpResponseContent)+'\n' )
	
			currentFile.close()
			f_out.write(f + '|' + 'Uploaded and moving to archive folder' + '\n')
			shutil.move(upDocPath, archivePath) #file has been uploaded move to an archive folder
		else:
			f_out.write(f +'| File was not uploaded, filename did not conform to designated standard. \n')	

	f_out.close()
	shutil.move(outFilePath,archivePath) 

if __name__ == "__main__":
	main()
