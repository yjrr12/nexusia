NEXUS AI - VERSAO BASE SEM TRADING SKILLS

Esta versao preserva as paginas Mercado, Analise tecnica, Nexus AI, E-mail e alertas, Registros e Sobre. A funcao Trading skills / claude-trading-skills foi removida. O chat usa Groq no lugar do Ollama.

INSTALACAO LOCAL:
1. Instale Python 3.11 ou 3.12.
2. Abra o terminal nesta pasta.
3. Execute: python -m pip install -r requirements.txt
4. Configure GROQ_API_KEY como variavel de ambiente ou cole a chave no campo do chat.
5. Execute: streamlit run app.py

IMPORTANTE SOBRE VERCEL:
Este arquivo continua sendo Streamlit, igual ao projeto original. Streamlit nao e executado diretamente como uma aplicacao Next.js comum na Vercel. Para publicar na Vercel, e necessario portar a interface e as rotas para Next.js/Python serverless. O monitoramento em thread do Streamlit funciona enquanto o processo Streamlit estiver ativo; nao fica rodando continuamente em funcoes serverless.
