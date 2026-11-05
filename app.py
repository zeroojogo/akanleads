import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
import pandas as pd
import time
from urllib.parse import urljoin, urlparse

# ==========================================
# CONFIGURAÇÃO DA PÁGINA & IDENTIDADE AKAN
# ==========================================
st.set_page_config(
    page_title="Extrator B2B | Akan Investigações",
    page_icon="🕵️‍♂️",
    layout="wide"
)

# Estilização Customizada (Brutalista / Industrial Akan)
st.markdown("""
    <style>
    .main { background-color: #111111; }
    div.stButton > button:first-child {
        background-color: #d4af37;
        color: #111111;
        font-weight: 700;
        border: none;
        border-radius: 4px;
        padding: 0.6rem 1.2rem;
        width: 100%;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    div.stButton > button:first-child:hover {
        background-color: #b5952f;
        color: #111111;
    }
    .akan-header {
        border-bottom: 1px solid #333333;
        padding-bottom: 1rem;
        margin-bottom: 2rem;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }
    .gold-accent { color: #d4af37; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# Cabeçalho Institucional
col_logo, col_title = st.columns([1, 5])
with col_logo:
    st.image("https://www.akaninvestigacoes.com.br/assets/img/logo.png", width=110)
with col_title:
    st.markdown("<h2 style='margin-bottom:0; color:#ffffff; letter-spacing:1px;'>EXTRATOR DE LEADS B2B <span class='gold-accent'>| OUTBOUND</span></h2>", unsafe_allow_html=True)
    st.markdown("<p style='color:#888888; font-size:0.9rem;'>Mapeamento Automatizado de Escritórios de Advocacia & Extração de Contatos via Google Cloud API</p>", unsafe_allow_html=True)

st.divider()

# ==========================================
# FUNÇÕES DE EXTRAÇÃO E SCRAPING DE E-MAILS
# ==========================================
EMAIL_REGEX = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'

IGNORED_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.css', '.js', '.woff', '.woff2', '.ttf')
IGNORED_DOMAINS = ('sentry.io', 'wixpress.com', 'example.com', 'yourdomain.com', 'email.com', 'wordpress.org')

def limpar_emails(lista_bruta):
    emails_validos = set()
    for email in lista_bruta:
        email = email.lower().strip().rstrip('.')
        if not email.endswith(IGNORED_EXTENSIONS) and not any(d in email for d in IGNORED_DOMAINS):
            if len(email) <= 60:
                emails_validos.add(email)
    return list(emails_validos)

def extrair_emails_do_site(url):
    """Acessa a página inicial e a página de contato do escritório para capturar e-mails."""
    if not url or not isinstance(url, str):
        return []
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
    }
    emails_encontrados = set()
    
    try:
        resp = requests.get(url, headers=headers, timeout=7, verify=False)
        if resp.status_code == 200:
            html = resp.text
            emails_encontrados.update(re.findall(EMAIL_REGEX, html))
            
            # Se não achou na Home, procura links de "Contato" ou "Quem Somos"
            if not emails_encontrados:
                soup = BeautifulSoup(html, 'html.parser')
                for a in soup.find_all('a', href=True):
                    href = a['href'].lower()
                    if any(termo in href for termo in ['contato', 'contact', 'fale-conosco', 'escritorio', 'sobre']):
                        url_contato = urljoin(url, a['href'])
                        if urlparse(url_contato).netloc == urlparse(url).netloc:
                            resp_c = requests.get(url_contato, headers=headers, timeout=5, verify=False)
                            if resp_c.status_code == 200:
                                emails_encontrados.update(re.findall(EMAIL_REGEX, resp_c.text))
                            break
    except Exception:
        pass
        
    return limpar_emails(emails_encontrados)

def buscar_places_google(query, api_key, max_paginas=2):
    """Busca estabelecimentos na API do Google Maps (Text Search) e coleta detalhes."""
    url_textsearch = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    url_details = "https://maps.googleapis.com/maps/api/place/details/json"
    
    places = []
    params = {"query": query, "key": api_key, "language": "pt-BR"}
    
    for _ in range(max_paginas):
        res = requests.get(url_textsearch, params=params).json()
        if res.get("status") != "OK":
            break
            
        places.extend(res.get("results", []))
        next_page_token = res.get("next_page_token")
        if not next_page_token:
            break
            
        time.sleep(2)  # Delay exigido pelo Google para validar o next_page_token
        params = {"pagetoken": next_page_token, "key": api_key}
        
    leads_detalhados = []
    barra = st.progress(0, text="Consultando detalhes e varrendo sites em busca de e-mails...")
    total = len(places)
    
    for idx, place in enumerate(places):
        place_id = place.get("place_id")
        det_params = {
            "place_id": place_id,
            "fields": "name,formatted_address,formatted_phone_number,website,rating,user_ratings_total,url",
            "key": api_key,
            "language": "pt-BR"
        }
        det_res = requests.get(url_details, params=det_params).json().get("result", {})
        
        nome = det_res.get("name", place.get("name"))
        site = det_res.get("website", "")
        telefone = det_res.get("formatted_phone_number", "")
        endereco = det_res.get("formatted_address", place.get("formatted_address", ""))
        maps_url = det_res.get("url", "")
        avaliacao = det_res.get("rating", "")
        total_avaliacoes = det_res.get("user_ratings_total", 0)
        
        # Faz o scraping de e-mail se o escritório tiver site
        emails = extrair_emails_do_site(site) if site else []
        
        leads_detalhados.append({
            "Escritório / Empresa": nome,
            "E-mail Principal": emails[0] if emails else "",
            "Todos os E-mails": ", ".join(emails),
            "Telefone": telefone,
            "Website": site,
            "Endereço": endereco,
            "Avaliação": avaliacao,
            "Nº Reviews": total_avaliacoes,
            "Link Google Maps": maps_url
        })
        
        barra.progress((idx + 1) / total, text=f"Processando ({idx+1}/{total}): {nome}")
        
    barra.empty()
    return pd.DataFrame(leads_detalhados)

# ==========================================
# BARRA LATERAL (CONFIGURAÇÕES E CREDENCIAIS)
# ==========================================
with st.sidebar:
    st.markdown("### ⚙️ Configuração da Operação")
    
    # Tenta puxar dos Secrets do Streamlit; se não existir, libera input na tela
    default_key = st.secrets.get("GOOGLE_MAPS_API_KEY", "") if "GOOGLE_MAPS_API_KEY" in st.secrets else ""
    api_key = st.text_input("Google Cloud Maps API Key", value=default_key, type="password", help="Habilite a Places API no seu console do Google Cloud.")
    
    st.markdown("---")
    st.markdown("### 🎯 Presets de Busca (Akan)")
    nicho_selecionado = st.selectbox(
        "Segmento Jurídico / Alvo",
        [
            "Escritório de Advocacia Empresarial",
            "Advocacia Recuperação de Crédito e Execução",
            "Escritório de Advocacia Contencioso Cível",
            "Advocacia Direito Bancário e Empresarial",
            "Administradora Judicial / Falências",
            "Personalizado (Digitar manualmente)"
        ]
    )
    
    if nicho_selecionado == "Personalizado (Digitar manualmente)":
        termo_nicho = st.text_input("Digite o nicho:", placeholder="Ex: Escritório de Advocacia Societário")
    else:
        termo_nicho = nicho_selecionado
        
    cidade_alvo = st.text_input("Cidade / Região Alvo", value="Porto Alegre, RS", placeholder="Ex: São Paulo - Jardins / Faria Lima")
    
    max_paginas = st.slider("Profundidade da Busca (Páginas da API)", min_value=1, max_value=3, value=1, help="1 página = até 20 leads | 3 páginas = até 60 leads por busca.")
    apenas_com_email = st.checkbox("Filtrar apenas leads com e-mail encontrado", value=False)

# ==========================================
# ÁREA PRINCIPAL DE EXECUÇÃO E EXPORTAÇÃO
# ==========================================
query_final = f"{termo_nicho} em {cidade_alvo}"
st.markdown(f"**Query de Busca Ativa:** `{query_final}`")

if st.button("🚀 INICIAR MAPEAMENTO E EXTRAÇÃO"):
    if not api_key:
        st.error("Insira sua chave da API do Google Maps na barra lateral (ou configure no Streamlit Secrets).")
    elif not cidade_alvo:
        st.warning("Informe a cidade ou região alvo para iniciar a varredura.")
    else:
        with st.spinner("Conectando à Google Places API e iniciando crawler..."):
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            
            df_resultado = buscar_places_google(query_final, api_key, max_paginas=max_paginas)
            
            if df_resultado.empty:
                st.warning("Nenhum resultado retornado pela API. Verifique se a 'Places API' está ativa e se o faturamento da conta Cloud está liberado.")
            else:
                if apenas_com_email:
                    df_resultado = df_resultado[df_resultado["E-mail Principal"] != ""]
                
                st.session_state["df_leads_akan"] = df_resultado

# Exibição de Resultados se já houver busca na sessão
if "df_leads_akan" in st.session_state and not st.session_state["df_leads_akan"].empty:
    df = st.session_state["df_leads_akan"]
    
    total_leads = len(df)
    com_site = len(df[df["Website"] != ""])
    com_email = len(df[df["E-mail Principal"] != ""])
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Total de Escritórios Mapeados", total_leads)
    c2.metric("Possuem Website", com_site)
    c3.metric("E-mails Extraídos", com_email)
    
    st.dataframe(df, use_container_width=True, hide_index=True)
    
    st.markdown("### 📥 Exportar Base para o Motor de Disparos")
    col_dl1, col_dl2 = st.columns(2)
    
    # CSV completo
    csv_completo = df.to_csv(index=False).encode('utf-8-sig')
    with col_dl1:
        st.download_button(
            label="Baixar Planilha Completa (.CSV)",
            data=csv_completo,
            file_name=f"leads_akan_{cidade_alvo.replace(' ', '_').lower()}.csv",
            mime="text/csv"
        )
        
    # CSV limpo só com quem tem e-mail (Pronto pro PHPMailer)
    df_disparo = df[df["E-mail Principal"] != ""][["Escritório / Empresa", "E-mail Principal", "Telefone", "Website"]]
    csv_disparo = df_disparo.to_csv(index=False).encode('utf-8-sig')
    with col_dl2:
        st.download_button(
            label="⚡ Baixar Lista Limpa para PHPMailer (.CSV)",
            data=csv_disparo,
            file_name=f"disparo_akan_{cidade_alvo.replace(' ', '_').lower()}.csv",
            mime="text/csv"
        )