# Deploy no Streamlit Community Cloud — Passo a Passo

## 1. Criar conta no GitHub
Se ainda não tiver: https://github.com/signup

---

## 2. Criar repositório no GitHub

1. Acesse https://github.com/new
2. Nome do repo: `odds-monitor`
3. Marque **Public**
4. Clique em **Create repository**
5. Faça upload dos 2 arquivos:
   - `app.py`
   - `requirements.txt`

---

## 3. Criar conta no Streamlit Cloud

1. Acesse https://share.streamlit.io
2. Clique em **Sign up** e entre com sua conta GitHub

---

## 4. Deploy do app

1. Clique em **New app**
2. Selecione o repositório `odds-monitor`
3. Branch: `main`
4. Main file path: `app.py`
5. Clique em **Deploy**

Aguarde ~1 minuto. O app estará disponível em:
```
https://[seu-usuario]-odds-monitor-app-[hash].streamlit.app
```

---

## 5. Configurar credenciais com segurança (Secrets)

No Streamlit Cloud, **nunca cole credenciais direto no código**.
Use o sistema de Secrets:

1. No painel do app, clique em ⚙️ **Settings → Secrets**
2. Cole:
```toml
ODDS_API_KEY = "sua_chave_aqui"
TELEGRAM_TOKEN = "seu_token_aqui"
TELEGRAM_CHAT_ID = "seu_chat_id_aqui"
```
3. Clique em **Save**

> As credenciais ficam seguras e não aparecem no código.

---

## 6. Uso local (opcional)

```bash
pip install streamlit requests pandas
streamlit run app.py
```

Acesse: http://localhost:8501

---

## Observações

- O Streamlit Cloud é **gratuito** para apps públicos
- Para manter privado, use o plano Teams (pago)
- O app fica ativo enquanto alguém estiver com a aba aberta
- Para rodar 24/7 sem precisar manter o browser aberto, considere hospedar em Railway.app ou Render.com (planos gratuitos disponíveis)
