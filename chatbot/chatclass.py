# libreries
import os
import re
import time
import warnings

import requests
from dotenv import load_dotenv
from langchain import SQLDatabase
from langchain.memory import ConversationBufferWindowMemory
from sqlalchemy import create_engine, inspect

from tools import logger

from .prompts import question_prompt_template, sql_prompt_template, system_prompt_template

warnings.filterwarnings('ignore')


load_dotenv(override=True)

URI = os.getenv('URI')
FAB_USER_ID = os.getenv('FAB_USER_ID')
FAB_API_KEY = os.getenv('FAB_API_KEY')
FAB_AGENT_URL = os.getenv('FAB_AGENT_URL')



class Text2SQL:

    def __init__(self):

        logger.info('Iniciar Chat')

        missing_fab_settings = [
            name
            for name, value in (
                ('FAB_USER_ID', FAB_USER_ID),
                ('FAB_API_KEY', FAB_API_KEY),
                ('FAB_AGENT_URL', FAB_AGENT_URL),
            )
            if not value or not value.strip()
        ]
        if missing_fab_settings:
            raise RuntimeError(
                f"Faltan variables de entorno requeridas: {', '.join(missing_fab_settings)}"
            )
        
        self.tables = inspect(create_engine(URI)).get_table_names(schema='dbo')
        self.db = SQLDatabase.from_uri(URI, schema='dbo', sample_rows_in_table_info=2, include_tables=self.tables)
        self.sql_query = None
        self.last_sql_query = None
        self.context = None
        self.memory = ConversationBufferWindowMemory(k=4, return_messages=True)
    

    def call_fab_agent(self, query: str, custom_prompt: str) -> object:

        headers = {
            'content-type': 'application/json',
            'x-user-id': FAB_USER_ID,
            'x-authentication': f'api-key {FAB_API_KEY}',
        }
        payload = {'input': {'query': query, 'custom_prompt': custom_prompt}}

        try:
            response = requests.post(
                FAB_AGENT_URL,
                headers=headers,
                json=payload,
                timeout=(5, 60),
            )
            response.raise_for_status()
        except requests.exceptions.Timeout as error:
            raise RuntimeError('Tiempo de espera agotado al llamar al agente FAB.') from error
        except requests.exceptions.HTTPError as error:
            status_code = error.response.status_code if error.response is not None else 'desconocido'
            raise RuntimeError(f'El agente FAB respondió con HTTP {status_code}.') from error
        except requests.exceptions.RequestException as error:
            raise RuntimeError('No se pudo conectar con el agente FAB.') from error

        try:
            return response.json()
        except requests.exceptions.JSONDecodeError as error:
            raise RuntimeError('El agente FAB devolvió una respuesta que no es JSON válido.') from error


    @staticmethod
    def _extract_agent_text(agent_response: object) -> str:
        if isinstance(agent_response, str):
            return agent_response

        if isinstance(agent_response, dict):
            for key in ('output', 'response', 'result', 'content', 'text', 'answer'):
                if key in agent_response:
                    try:
                        return Text2SQL._extract_agent_text(agent_response[key])
                    except RuntimeError:
                        continue

        if isinstance(agent_response, list):
            for item in agent_response:
                try:
                    return Text2SQL._extract_agent_text(item)
                except RuntimeError:
                    continue

        raise RuntimeError('La respuesta del agente FAB no contiene texto.')


    def create_sql_query(self, prompt: str) -> str:

        """
        Metodo para crear query de SQL, actualiza el atributo self.sql_query

        Params: prompt, str, consulta del usuario

        Return: None
        """

        logger.info('Creando query...')

        custom_prompt = sql_prompt_template.format(
            dialect=self.db.dialect,
            top_k=5,
            last_query=self.last_sql_query or 'Ninguna',
            table_names=', '.join(self.tables),
            table_info=self.db.get_table_info(),
            input=prompt,
        )
        agent_response = self.call_fab_agent(query=prompt, custom_prompt=custom_prompt)
        agent_text = self._extract_agent_text(agent_response).strip()

        sql_block = re.search(r'```(?:sql)?\s*(.*?)```', agent_text, re.IGNORECASE | re.DOTALL)
        sql_query = (sql_block.group(1) if sql_block else agent_text).strip()

        has_write_statement = re.search(
            r'\b(?:create|drop|delete|alter|insert|update|merge|exec(?:ute)?)\b',
            sql_query,
            re.IGNORECASE,
        )
        starts_with_read_statement = re.match(r'\s*(?:select|with)\b', sql_query, re.IGNORECASE)

        if not starts_with_read_statement or has_write_statement:
            self.sql_query = 'SELECT "Actua como un asistente, usa la memoria"'
        else:
            self.sql_query = sql_query

        logger.info('Query creada!')
    

    def execute_and_check_query(self, prompt: str) -> None:

        """
        Metodo para ejecutar la query de SQL 

        Params: prompt, str, consulta del usuario

        Return: None, actualiza el atributo contexto
        """

        logger.info('Creacion y ejecución de la query...')

        max_attempts = 3
        retry_prompt = prompt

        for attempt in range(1, max_attempts + 1):
            try:
                self.create_sql_query(retry_prompt)
                logger.info(f'SQL query: {self.sql_query}')

                if self.sql_query == 'SELECT "Actua como un asistente, usa la memoria"':
                    self.context = self.sql_query
                    return

                context = self.db.run(self.sql_query)
                if context:
                    self.context = context
                    logger.info('Contexto creado')
                    return

                logger.info('Contexto vacio, se reintentara la consulta SQL.')
                retry_prompt = (
                    f'El prompt {prompt} genero la query {self.sql_query}, pero no devolvio resultados. '
                    'Reformula y simplifica la query para devolver resultados.'
                )
            except Exception as error:
                logger.info(f'Fallo en generacion o ejecucion SQL, intento {attempt}/{max_attempts}: {error}')
                retry_prompt = (
                    f'El prompt {prompt} genero la query {self.sql_query}, pero fallo con este error: {error}. '
                    'Corrige la consulta para el prompt original.'
                )
                if attempt < max_attempts:
                    time.sleep(min(2 ** (attempt - 1), 8))

        logger.info('Se agotaron los reintentos de SQL; se usara el modo de memoria.')
        self.sql_query = 'SELECT "Actua como un asistente, usa la memoria"'
        self.context = self.sql_query


    def generate_final_response(self, prompt: str) -> str:
        history = self.memory.load_memory_variables({})['history']
        history_text = '\n'.join(
            f"{'Usuario' if message.type == 'human' else 'Asistente'}: {message.content}"
            for message in history
        )
        query = question_prompt_template.format(
            sql_query=self.sql_query,
            context=self.context,
            prompt=prompt,
        )
        if history_text:
            query = f'Historial de conversación:\n{history_text}\n\n{query}'

        response = self.call_fab_agent(query=query, custom_prompt=system_prompt_template)
        return self._extract_agent_text(response).strip()
    

    def main(self, prompt: str):

        self.execute_and_check_query(prompt)

        try:
            logger.info('Generando respuesta...')
            response = self.generate_final_response(prompt)
        except Exception as error:
            try:
                logger.info(f'Recuperando memoria...Error: {error}')
                history = self.memory.load_memory_variables({})['history']
                if len(history) >= 2:
                    last_messages = history[-2:]
                    self.memory = ConversationBufferWindowMemory(k=4, return_messages=True)
                    self.memory.save_context({'question': last_messages[-2].content}, {'response': last_messages[-1].content})
                else:
                    self.memory = ConversationBufferWindowMemory(k=4, return_messages=True)
                response = self.generate_final_response(prompt)
            except Exception as retry_error:
                logger.info(f'Respuesta por defecto, no se pudo consultar FAB. Error: {retry_error}')
                self.memory = ConversationBufferWindowMemory(k=4, return_messages=True)
                response = 'No se pudo generar una respuesta ahora. Inténtalo de nuevo más tarde.'

        yield response
        self.memory.save_context({'question': prompt}, {'response': response})

        self.last_sql_query = self.sql_query
        self.sql_query = None
        self.context = None
        logger.info('Hecho')
