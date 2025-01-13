import streamlit as st
import pandas as pd
from pathlib import Path

from langchain.agents import create_sql_agent
from langchain.sql_database import SQLDatabase

from langchain.agents.agent_types import AgentType
from langchain.callbacks import StreamlitCallbackHandler
from langchain.agents.agent_toolkits import SQLDatabaseToolkit
from langchain.output_parsers import PydanticOutputParser
from pydantic import BaseModel

from sqlalchemy import create_engine
import sqlite3

from langchain_openai import ChatOpenAI
from langchain_groq import ChatGroq
import time
import os



# Title
st.set_page_config(page_title="The",page_icon="Icon")
st.title("SQLMate🦜🔗")


local_db = "Use_local_db"
mysql = "Use_MySQL"
cloud_sql = "Use_Cloud_SQL"

## Radio button to select the database
radio_opt = ["Local Database", "MySQL", "Cloud SQL"]
db_option = st.sidebar.radio("Select the database", options=radio_opt)

if db_option == "MySQL":
    db_uri = mysql
    host = st.sidebar.text_input("Host", "localhost")
    user = st.sidebar.text_input("User", "root")
    password = st.sidebar.text_input("Password", "", type="password")
    mysql_db = st.sidebar.text_input("Database", "sample")

# If user wants to use sqlite database
elif db_option == "Local Database":
    file_name = st.sidebar.text_input("Enter the file name")
    db_uri = local_db
else:
    st.title("Cloud SQL Coming Soooooooon...")
    st.stop()


# API key for OpenAI and GROQ give option to user to select the API
api_option = ["OpenAI", "GROQ"]
api = st.sidebar.radio("Select the API", options=api_option)

if api == "OpenAI":
    api_key = st.sidebar.text_input("OpenAI API Key", "", type="password")
    os.environ['OPENAI_API_KEY']=api_key
    model = st.sidebar.selectbox("Select the OpenAI model",["gpt-4o","gpt-4o-mini","o1","o1-mini"])
    llm = ChatOpenAI(model=model,streaming=True)
else:
    api_key = st.sidebar.text_input("GROQ API Key", "", type="password")
    model = st.sidebar.selectbox("Select the model",["llama-3.3-70b-versatile","llama3-8b-8192", "gemma2-9b-it", "mixtral-8x7b-32768"])
    os.environ['GROQ_API_KEY']=api_key
    llm = ChatGroq(model_name=model,streaming=True)
    
if not db_uri:
    st.error("Please select the database")
    st.stop()

if not api_key:
    st.error("Please enter the API key")
    st.stop()

## Caching db info
@st.cache_resource(ttl="2h")
def configure_db(db_uri,file_name=None,host=None,user=None,password=None,mysql_db=None):
    if db_uri == "Use_local_db":
        try:
            dbfilepath = (Path(__file__).parent/file_name).absolute()
            # st.write(dbfilepath)
            creator = lambda:sqlite3.connect(f"file:{dbfilepath}?mode=ro",uri=True)
            return SQLDatabase(create_engine("sqlite:///",creator=creator))
        except Exception as e:
            st.error(f"Error occured during Sqlite3 config => {e}")
            st.stop()

    elif db_uri == "Use_MySQL":

        if not (host and user and password and mysql_db):
            st.error("Please provide MySQL connection details")
            st.stop()
        else:
            try:
                connection_string = f"mysql+mysqlconnector://{user}:{password}@{host}/{mysql_db}"
                sqlengine= create_engine(connection_string)
                return SQLDatabase(sqlengine)
            except Exception as e:
                st.error(f"Error connecting to MySQL: {e}")
                st.stop()
    
if db_uri == "Use_MySQL":
    db = configure_db(db_uri,host=host,user=user,password=password,mysql_db=mysql_db)
elif db_uri == "Use_local_db":
    db = configure_db(db_uri,file_name)

## Parsing the output
class SQLQuery(BaseModel):
    query:str

output_parser = PydanticOutputParser(pydantic_object=SQLQuery)


## Toolkit
toolkit = SQLDatabaseToolkit(db=db,llm=llm)
agent = create_sql_agent(
    llm = llm,
    toolkit = toolkit,
    verbose = True,
    agent_type = AgentType.ZERO_SHOT_REACT_DESCRIPTION, # gives response without previos context
    output_parser = output_parser
    
)

## Creating session state to maintain chat history
if "message" not in st.session_state or st.sidebar.button("Clear chat"):
    st.session_state["message"] = [{"role":"assistant","content":"How can I help you?"}]
    
## Appending chat msgs
for msg in st.session_state.message:
    st.chat_message(msg["role"]).write(msg["content"])
    


## Asking the db
user_query  = st.chat_input(placeholder="Chat with your Database")


if(user_query):
    st.session_state.message.append({"role":"user","content":user_query})
    st.chat_message("user").write(user_query)
    
    with st.chat_message("assistant"):
        stream_callbacks = StreamlitCallbackHandler(st.container()) ## Display chain of though/working
        start_time = time.time()
        response = agent.run(user_query,callbacks=[stream_callbacks])
        end_time = time.time()
        st.write(f"Time taken: {end_time-start_time}")
        st.session_state.message.append({"role":"assistant","content":response}) # Feeding the memory
        st.write(response)