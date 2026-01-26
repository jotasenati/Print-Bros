import time
import streamlit as st
import extra_streamlit_components as stx
import requests
import smtplib 
import pandas as pd 
from email.mime.text import MIMEText 
from email.mime.multipart import MIMEMultipart 
from fpdf import FPDF
from datetime import datetime, timedelta
from supabase import create_client, Client

# --- CONFIGURAÇÕES SUPABASE ---
SUPABASE_URL = "https://heirrnnbgkslndpyyjlx.supabase.co"
SUPABASE_KEY = "sb_secret_Hmuo25aRe-CAEvG852vcFg_qbtkgEE-" 

try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error(f"Erro na conexão com Supabase: {e}")

# --- CONFIG PAGE ---
st.set_page_config(page_title="PRINT BROS - Gestor", layout="wide")

# --- COOKIE MANAGER ---
cookie_manager = stx.CookieManager()

# --- AUTENTICAÇÃO ---
def autenticar():
    user_cookie = cookie_manager.get(cookie="pb_user_nome")
    if user_cookie is None:
        time.sleep(0.1)
        user_cookie = cookie_manager.get(cookie="pb_user_nome")

    if "autenticado" not in st.session_state:
        if user_cookie:
            st.session_state["autenticado"] = True
            st.session_state["usuario_nome"] = user_cookie
        else:
            st.session_state["autenticado"] = False

    if not st.session_state["autenticado"]:
        st.markdown("### 🔐 PRINT BROS - Login")
        with st.form("login_form"):
            user_input = st.text_input("Usuário")
            pass_input = st.text_input("Senha", type="password")
            lembrar = st.checkbox("Manter conectado", value=True)
            
            if st.form_submit_button("Acessar Sistema"):
                res = supabase.table("usuarios").select("*").eq("username", user_input).eq("password", pass_input).execute()
                if res.data:
                    nome_usuario = res.data[0]['nome']
                    st.session_state["autenticado"] = True
                    st.session_state["usuario_nome"] = nome_usuario
                    
                    if lembrar:
                        cookie_manager.set("pb_user_nome", nome_usuario, 
                                       expires_at=datetime.now() + timedelta(days=7))
                    st.rerun()
                else:
                    st.error("Usuário ou senha incorretos.")
        return False
    return True

# --- FUNÇÕES AUXILIARES ---
def formatar_moeda(valor):
    try:
        return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return "R$ 0,00"

def upload_comprovante(pedido_id, arquivo):
    try:
        file_path = f"comprovante_{pedido_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
        supabase.storage.from_("comprovantes").upload(file_path, arquivo.read(), {"content-type": arquivo.type})
        return supabase.storage.from_("comprovantes").get_public_url(file_path)
    except Exception as e:
        st.error(f"Erro no upload: {e}")
        return None

# --- FUNÇÃO DE ENVIO DE E-MAIL ---
def enviar_alerta_baixo_estoque(material, cor, marca, peso_restante):
    try:
        if "email" not in st.secrets:
            return False

        remetente = st.secrets["email"]["usuario"]
        senha = st.secrets["email"]["senha"]
        destinatario = st.secrets["email"]["destinatario"]

        assunto = f"⚠️ ALERTA DE COMPRA: {material} {cor} ({peso_restante}g)"
        corpo = f"""
        Olá,
        
        O sistema Print Bros detectou estoque baixo durante a produção de um pedido.
        
        📦 Material: {material}
        🎨 Cor: {cor}
        🏷️ Marca: {marca}
        ⚖️ Peso Restante: {peso_restante}g
        
        Necessário realizar compra de reposição.
        """

        msg = MIMEMultipart()
        msg['From'] = remetente
        msg['To'] = destinatario
        msg['Subject'] = assunto
        msg.attach(MIMEText(corpo, 'plain'))

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(remetente, senha)
        text = msg.as_string()
        server.sendmail(remetente, destinatario, text)
        server.quit()
        
        return True
    except Exception as e:
        print(f"Erro ao enviar email: {e}") 
        return False

# --- FUNÇÃO PARA BAIXA DE ESTOQUE ---
def dar_baixa_estoque(itens_pedido):
    log_baixa = []
    
    for item in itens_pedido:
        quantidade_item = int(item.get("quantidade", 1))
        
        # Verifica se é um item multi-material (nova estrutura)
        lista_materiais = item.get("componentes", [])
        
        # Se não tiver lista (legado ou manual simples), tenta montar uma lista com o item único
        if not lista_materiais and item.get("stock_id"):
            lista_materiais = [{
                "stock_id": item.get("stock_id"),
                "gramas": item.get("gramas", 0),
                "nome_mat": item.get("material", "Material")
            }]

        # Processa a baixa de cada componente
        for componente in lista_materiais:
            stock_id = componente.get("stock_id")
            gramas_unitario = float(componente.get("gramas", 0))
            
            if stock_id and gramas_unitario > 0:
                peso_total_descontar = gramas_unitario * quantidade_item
                
                try:
                    res = supabase.table("estoque_filamentos").select("*").eq("id", stock_id).execute()
                    if res.data:
                        dados_filamento = res.data[0]
                        atual = float(dados_filamento['peso_restante_g'])
                        novo_peso = atual - peso_total_descontar
                        
                        supabase.table("estoque_filamentos").update({"peso_restante_g": novo_peso}).eq("id", stock_id).execute()
                        
                        log_baixa.append(f"✅ {dados_filamento['material']} {dados_filamento['cor']}: -{peso_total_descontar:.1f}g (Rest: {novo_peso:.1f}g)")

                        LIMITE_ALERTA = 500.0
                        if novo_peso <= LIMITE_ALERTA:
                            enviar_alerta_baixo_estoque(
                                dados_filamento['material'],
                                dados_filamento['cor'],
                                dados_filamento.get('marca', 'Genérica'),
                                novo_peso
                            )
                    else:
                        log_baixa.append(f"⚠️ ID {stock_id} não encontrado no estoque.")
                except Exception as e:
                    log_baixa.append(f"❌ Erro ao baixar ID {stock_id}: {e}")
            
    return log_baixa

# --- CONSTANTES ---
MAQUINAS = {"Bambu Lab A1 Mini": 150, "Anycubic Kobra 3 + ACE Pro": 400}
COR_LARANJA = (244, 161, 130)
COR_CIANO = (148, 211, 204)
TELEFONE_EMPRESA = "11 5194-7240"

def clean(txt):
    return str(txt).encode('latin-1', 'replace').decode('latin-1')

# --- PDF GENERATOR ---
class PrintBrosPDF(FPDF):
    def header(self):
        self.set_fill_color(*COR_LARANJA)
        self.rect(0, 0, 210, 15, 'F')
        try:
            self.image('logo.png', 12, 20, 35) 
        except:
            self.set_xy(10, 20)
            self.set_font("Helvetica", "B", 18)
            self.set_text_color(*COR_LARANJA)
            self.cell(50, 10, "PRINT BROS", ln=False)
        
        self.set_xy(110, 20)
        self.set_font("Helvetica", "B", 22)
        self.set_text_color(40, 40, 40)
        self.cell(90, 15, clean("ORÇAMENTO"), align='R', ln=True)
        
        self.set_draw_color(*COR_CIANO)
        self.set_line_width(0.5)
        self.line(10, 42, 200, 42)
        self.ln(15)

    def footer(self):
        self.set_y(-30)
        self.set_draw_color(200, 200, 200)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(5)
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(60, 60, 60)
        resp = st.session_state.get("usuario_nome", "Departamento Comercial")
        self.cell(0, 5, clean(f"Responsável: {resp.upper()}"), align='C', ln=True)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 5, clean(f"PRINT BROS - Contato: {TELEFONE_EMPRESA} | Página {self.page_no()}/{{nb}}"), align='C')

def gerar_pdf(dados_cliente, itens, prazo):
    pdf = PrintBrosPDF()
    pdf.alias_nb_pages()
    pdf.add_page()
    
    # BOX CLIENTE
    pdf.set_fill_color(250, 250, 250)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(*COR_LARANJA)
    pdf.cell(0, 8, clean("DADOS DO CLIENTE"), ln=True, fill=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(50, 50, 50)
    pdf.cell(0, 6, clean(f"Nome: {dados_cliente.get('nome', 'Consumidor').upper()}"), ln=True)
    pdf.cell(0, 6, clean(f"Telefone: {dados_cliente.get('telefone', 'Não informado')}"), ln=True)
    pdf.cell(0, 6, clean(f"Emissão: {datetime.now().strftime('%d/%m/%Y %H:%M')}"), ln=True)
    pdf.ln(8)

    # TABELA
    pdf.set_fill_color(60, 60, 60)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(95, 10, clean(" DESCRIÇÃO DO SERVIÇO / PEÇA"), border=0, fill=True)
    pdf.cell(35, 10, clean("MATERIAL"), border=0, fill=True, align='C')
    pdf.cell(20, 10, clean("QTD"), border=0, fill=True, align='C')
    pdf.cell(40, 10, clean("TOTAL "), border=0, fill=True, align='R', ln=True)

    pdf.set_text_color(50, 50, 50)
    pdf.set_font("Helvetica", "", 10)
    total_geral = 0
    zebra = False
    
    for item in itens:
        v_unit = float(item.get('preco_final_unitario', 0))
        qtd = int(item.get('quantidade', 1))
        subtotal = v_unit * qtd
        total_geral += subtotal
        
        bg_color = (245, 245, 245) if zebra else (255, 255, 255)
        pdf.set_fill_color(*bg_color)
        
        pdf.cell(95, 9, clean(f" {item['nome']}"), border='B', fill=True)
        pdf.cell(35, 9, clean(item['material']), border='B', fill=True, align='C')
        pdf.cell(20, 9, str(qtd), border='B', fill=True, align='C')
        pdf.cell(40, 9, formatar_moeda(subtotal) + " ", border='B', fill=True, align='R', ln=True)
        zebra = not zebra

    pdf.ln(10)
    pdf.set_x(130)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_fill_color(*COR_LARANJA)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(70, 12, clean(f" TOTAL GERAL: {formatar_moeda(total_geral)}"), align='C', fill=True)
    
    pdf.set_xy(10, pdf.get_y() + 5)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(100, 100, 100)
    pdf.multi_cell(110, 4, clean("Validade deste orçamento: 7 dias.\nPrazo de produção estimado após aprovação do pagamento."))
    return pdf.output(dest='S').encode('latin-1')

# --- INÍCIO DO APP ---
if autenticar():
    if 'carrinho' not in st.session_state: st.session_state.carrinho = []
    if 'cli_temp' not in st.session_state: st.session_state.cli_temp = {"nome": "Consumidor", "telefone": ""}

    menu = st.sidebar.radio("Navegação", [
        "📊 Dashboard", 
        "Calculadora", 
        "📦 Estoque de Filamentos", 
        "Clientes", 
        "Histórico de Orçamentos", 
        "📦 Pedidos (Produção)"
    ])
    
    if st.sidebar.button("Sair"):
        st.session_state["autenticado"] = False
        st.rerun()

    # --- TELA: DASHBOARD FINANCEIRO ---
    if menu == "📊 Dashboard":
        st.title("📊 Dashboard Financeiro")
        
        res = supabase.table("pedidos").select("valor_total, criado_em, status").execute()
        pedidos_data = res.data
        
        if pedidos_data:
            df = pd.DataFrame(pedidos_data)
            df['valor_total'] = pd.to_numeric(df['valor_total'])
            df['criado_em'] = pd.to_datetime(df['criado_em'])
            
            # --- NOVA LÓGICA DE FILTRO POR MÊS ---
            # Cria coluna mês/ano para o filtro
            df['mes_ano'] = df['criado_em'].dt.strftime('%m/%Y')
            
            # Obtém lista de meses únicos ordenados (mais recente primeiro)
            opcoes_meses = sorted(df['mes_ano'].unique(), reverse=True)
            opcoes_meses.insert(0, "Todos os Períodos")
            
            # Selectbox do filtro
            filtro_mes = st.selectbox("📅 Filtrar Período", options=opcoes_meses)
            
            # Aplica o filtro no DataFrame
            if filtro_mes != "Todos os Períodos":
                df_filtrado = df[df['mes_ano'] == filtro_mes]
                st.caption(f"Exibindo dados de: {filtro_mes}")
            else:
                df_filtrado = df
                st.caption("Exibindo dados gerais (Todo o período)")

            # --- CÁLCULO DOS KPIs COM O DATAFRAME FILTRADO ---
            df_filtrado['data_apenas'] = df_filtrado['criado_em'].dt.date
            
            total_pedidos = len(df_filtrado)
            total_vendas = df_filtrado['valor_total'].sum()
            ticket_medio = total_vendas / total_pedidos if total_pedidos > 0 else 0
            
            col1, col2, col3 = st.columns(3)
            col1.metric("📦 Total de Pedidos", total_pedidos)
            col2.metric("💰 Faturamento", formatar_moeda(total_vendas))
            col3.metric("🎫 Ticket Médio", formatar_moeda(ticket_medio))
            
            st.divider()
            
            c_graf1, c_graf2 = st.columns(2)
            
            with c_graf1:
                st.subheader("📈 Vendas por Dia")
                if not df_filtrado.empty:
                    vendas_por_dia = df_filtrado.groupby('data_apenas')['valor_total'].sum()
                    st.bar_chart(vendas_por_dia, color="#F4A182") 
                else:
                    st.warning("Sem vendas neste período.")
                
            with c_graf2:
                st.subheader("📋 Status dos Pedidos")
                if not df_filtrado.empty:
                    status_count = df_filtrado['status'].value_counts()
                    st.bar_chart(status_count, color="#94D3CC") 
                else:
                    st.warning("Sem dados.")
        else:
            st.info("Ainda não há pedidos registrados para gerar gráficos.")

    # --- TELA: CALCULADORA ---
    # --- TELA: CALCULADORA (MULTI-MATERIAL) ---
    elif menu == "Calculadora":
        st.title("🖨️ Calculadora Multi-Material")
        
        col_a, col_b = st.columns([2, 1])
        with col_a:
            tipo_orc = st.radio("Tipo de Orçamento:", ["Rápido (Sem cadastro)", "Profissional (Banco)"], horizontal=True)
        
        # --- LÓGICA DE SELEÇÃO DE CLIENTE ---
        if tipo_orc == "Profissional (Banco)":
            busca = st.text_input("🔍 Pesquisar cliente (3 letras...)")
            if len(busca) >= 3:
                res = supabase.table("clientes").select("*").ilike("nome", f"%{busca}%").execute()
                if res.data:
                    opcoes = {c['nome']: c for c in res.data}
                    escolha = st.selectbox("Selecione:", ["Selecione..."] + list(opcoes.keys()))
                    if escolha != "Selecione...": st.session_state.cli_temp = opcoes[escolha]
        else:
            c1, c2 = st.columns(2)
            st.session_state.cli_temp['nome'] = c1.text_input("Nome do Cliente", value=st.session_state.cli_temp.get('nome', 'Consumidor'))
            st.session_state.cli_temp['telefone'] = c2.text_input("WhatsApp", value=st.session_state.cli_temp.get('telefone', ''))

        with st.container(border=True):
            st.subheader("🛠️ Configuração da Peça")
            
            # --- PARÂMETROS GERAIS ---
            c_par1, c_par2, c_par3 = st.columns(3)
            custo_kwh = c_par1.number_input("Custo Energia (R$/kWh)", value=0.73, step=0.01)
            margem_lucro = c_par2.number_input("Margem de Lucro (%)", value=100.0, step=5.0)
            taxa_fixa = c_par3.number_input("Taxa Fixa (R$)", value=15.0, step=1.0)
            
            st.divider()

            # --- CARREGAR ESTOQUE ---
            res_estoque = supabase.table("estoque_filamentos").select("*").eq("ativo", True).order("material").execute()
            
            # Opções para o Selectbox
            opcoes_estoque = {"(Vazio/Manual)": None}
            if res_estoque.data:
                for item in res_estoque.data:
                    marca_txt = item.get('marca', 'Genérica')
                    # Exibe: Creality - PLA - Preto (R$ 130.00/kg)
                    label = f"{marca_txt} - {item['material']} - {item['cor']} (R$ {item['preco_kg']:.2f}/kg)"
                    opcoes_estoque[label] = item

            # --- DADOS DA PEÇA E MÁQUINA ---
            c1, c2 = st.columns(2)
            n_p = c1.text_input("Nome da Peça")
            m_p = c2.selectbox("Máquina", list(MAQUINAS.keys()))
            
            st.markdown("#### 🎨 Materiais / Cores (Até 4)")
            
            # --- LOOP MULTI-MATERIAL (1 a 4) ---
            componentes_selecionados = []
            custo_total_materiais = 0.0
            peso_total_peca = 0.0
            nomes_resumo = [] # Para exibir no PDF "Preto, Azul, Branco"

            # Cria 4 linhas de seleção
            for i in range(1, 5):
                col_sel, col_gr = st.columns([3, 1])
                
                # Chaves únicas para cada widget (mat_1, mat_2...)
                sel_key = f"mat_{i}"
                gram_key = f"gram_{i}"
                
                with col_sel:
                    selecao = st.selectbox(f"Filamento #{i}", list(opcoes_estoque.keys()), key=sel_key)
                with col_gr:
                    gramas = st.number_input(f"Gramas #{i}", min_value=0.0, step=1.0, key=gram_key)
                
                # Cálculos deste slot específico
                dados_item = opcoes_estoque[selecao]
                
                if gramas > 0:
                    peso_total_peca += gramas
                    
                    if dados_item:
                        # Material do Estoque (Tem ID)
                        preco_kg = float(dados_item['preco_kg'])
                        custo_parcial = (preco_kg / 1000) * gramas
                        
                        # Adiciona à lista de componentes para baixa futura
                        componentes_selecionados.append({
                            "stock_id": dados_item['id'],
                            "material": f"{dados_item['material']} {dados_item['cor']}",
                            "gramas": gramas,
                            "custo": custo_parcial
                        })
                        nomes_resumo.append(dados_item['cor'])
                        custo_total_materiais += custo_parcial
                    else:
                        # Material Manual (Sem ID - Preço padrão R$ 130/kg)
                        PRECO_PADRAO = 130.0
                        custo_parcial = (PRECO_PADRAO / 1000) * gramas
                        
                        # Adiciona sem stock_id (apenas financeiro)
                        nomes_resumo.append("Manual")
                        custo_total_materiais += custo_parcial

            # --- CÁLCULO FINAL DA PEÇA ---
            # Tempo agora é global para a peça
            t_h = st.number_input("Tempo Total de Impressão (Horas)", min_value=0.0, step=0.1)
            
            custo_energia = (MAQUINAS[m_p] / 1000) * t_h * custo_kwh
            custo_base = custo_total_materiais + custo_energia
            venda_calculada = (custo_base * (1 + margem_lucro / 100)) + taxa_fixa
            
            # Exibição dos Custos
            st.info(f"⚖️ Peso: {peso_total_peca}g | ⚡ Energia: {formatar_moeda(custo_energia)} | 🧵 Material: {formatar_moeda(custo_total_materiais)}")
            
            v_final_manual = st.number_input("VALOR FINAL DE VENDA (R$)", min_value=0.0, value=round(venda_calculada, 2))
            
            if st.button("➕ Adicionar ao Carrinho"):
                if not n_p:
                    st.error("Digite o nome da peça.")
                elif peso_total_peca <= 0:
                    st.error("Adicione peso em pelo menos um filamento.")
                else:
                    # Monta string de exibição (Ex: "Preto, Amarelo")
                    str_materiais = ", ".join(nomes_resumo) if nomes_resumo else "Genérico"
                    
                    st.session_state.carrinho.append({
                        "id": datetime.now().timestamp(), 
                        "nome": n_p, 
                        "maquina": m_p, 
                        "material": str_materiais,       # Usado no PDF/Zap
                        "gramas": peso_total_peca,       # Peso total
                        "componentes": componentes_selecionados, # LISTA CRÍTICA P/ ESTOQUE
                        "preco_final_unitario": v_final_manual, 
                        "quantidade": 1
                    })
                    st.rerun()

        # --- EXIBIÇÃO DO CARRINHO ---
        if st.session_state.carrinho:
            st.subheader("📋 Itens Adicionados")
            total = sum(item['preco_final_unitario'] * item['quantidade'] for item in st.session_state.carrinho)
            
            for i, item in enumerate(st.session_state.carrinho):
                col_item, col_qtd, col_del = st.columns([4, 1, 1])
                with col_item:
                    # Mostra detalhes e materiais
                    st.write(f"**{item['nome']}** ({item['material']}) - {formatar_moeda(item['preco_final_unitario'])}")
                    if item.get('componentes'):
                        st.caption(f"🎨 {len(item['componentes'])} cores configuradas")
                
                with col_qtd:
                    nova_qtd = st.number_input("Qtd", min_value=1, value=int(item['quantidade']), key=f"qtd_{i}", label_visibility="collapsed")
                    if nova_qtd != item['quantidade']:
                        st.session_state.carrinho[i]['quantidade'] = nova_qtd
                        st.rerun()
                
                with col_del:
                    if st.button("🗑️", key=f"del_item_{i}"):
                        st.session_state.carrinho.pop(i)
                        st.rerun()
            
            st.markdown(f"### Total: {formatar_moeda(total)}")

            c1, c2, c3 = st.columns(3)
            
            # --- GERAR PDF ---
            dados_pdf_temp = {"nome": st.session_state.cli_temp.get('nome'), "telefone": st.session_state.cli_temp.get('telefone')}
            pdf_preview = gerar_pdf(dados_pdf_temp, st.session_state.carrinho, "7 dias")
            c1.download_button("📥 Baixar PDF", data=pdf_preview, file_name="Orcamento_Preview.pdf", use_container_width=True)

            # --- WHATSAPP ---
            nome_c = st.session_state.cli_temp.get('nome', 'Cliente')
            tel_c = st.session_state.cli_temp.get('telefone', '')
            if tel_c:
                import urllib.parse
                msg_whatsapp = f"Olá {nome_c}! Segue o orçamento: \n"
                for it in st.session_state.carrinho:
                    msg_whatsapp += f"- {it['quantidade']}x {it['nome']}: {formatar_moeda(it['preco_final_unitario'])}\n"
                msg_whatsapp += f"\n*Total: {formatar_moeda(total)}*"
                tel_limpo = "".join(filter(str.isdigit, tel_c))
                if not tel_limpo.startswith("55"): tel_limpo = "55" + tel_limpo
                link_wa = f"https://wa.me/{tel_limpo}?text={urllib.parse.quote(msg_whatsapp)}"
                c2.link_button("🟢 WhatsApp", link_wa, use_container_width=True)
            else:
                c2.warning("📱 Sem WhatsApp")

            # --- SALVAR ORÇAMENTO ---
            if c3.button("💾 Salvar no Banco", type="primary", use_container_width=True):
                dados = {
                    "valor_total": total, 
                    "itens": st.session_state.carrinho, # Salva o carrinho com a lista 'componentes' dentro
                    "cliente_nome_manual": st.session_state.cli_temp['nome'], 
                    "cliente_id": st.session_state.cli_temp.get('id'),
                    "criado_por": st.session_state.get("usuario_nome", "Não identificado")
                }
                supabase.table("orcamentos").insert(dados).execute()
                st.success("Orçamento gravado no histórico!")
                st.session_state.carrinho = []
                st.rerun()

    # --- TELA: ESTOQUE ---
    elif menu == "📦 Estoque de Filamentos":
        st.title("📦 Gestão de Estoque")
        
        tab1, tab2 = st.tabs(["Meu Estoque", "Adicionar Novo"])
        
        with tab1:
            res = supabase.table("estoque_filamentos").select("*").execute()
            items_estoque = res.data if res.data else []

            if items_estoque:
                col_filtro, col_ordem = st.columns([2, 1])
                marcas_unicas = sorted(list(set([i['marca'] for i in items_estoque if i.get('marca')])))
                
                with col_filtro:
                    filtro_marca = st.multiselect("🔍 Filtrar por Marca", options=marcas_unicas)
                
                with col_ordem:
                    ordenacao = st.radio("Ordenação (Qtd Restante)", ["Maior p/ Menor", "Menor p/ Maior"], horizontal=True)

                if filtro_marca:
                    items_estoque = [i for i in items_estoque if i.get('marca') in filtro_marca]
                
                reverso = True if ordenacao == "Maior p/ Menor" else False
                items_estoque.sort(key=lambda x: float(x['peso_restante_g']), reverse=reverso)

                st.divider()
                st.caption(f"Exibindo {len(items_estoque)} carretéis.")

                for item in items_estoque:
                    status_cor = "🟢" if item['ativo'] else "🔴"
                    alerta_txt = "⚠️ BAIXO" if float(item['peso_restante_g']) <= 500 else ""
                    
                    marca_display = item.get('marca', 'Genérica')
                    titulo_expander = f"{status_cor} {marca_display} - {item['material']} - {item['cor']} | Restante: {item['peso_restante_g']}g {alerta_txt}"

                    with st.expander(titulo_expander):
                        with st.form(key=f"edit_stock_{item['id']}"):
                            col1, col2, col3 = st.columns(3)
                            n_mat = col1.text_input("Material", value=item['material'])
                            n_cor = col2.text_input("Cor", value=item['cor'])
                            n_marca = col3.text_input("Marca", value=item.get('marca', ''))
                            
                            col4, col5, col6 = st.columns(3)
                            n_peso = col4.number_input("Peso Restante (g)", value=float(item['peso_restante_g']))
                            n_preco = col5.number_input("Preço Pago (R$/kg)", value=float(item['preco_kg']))
                            n_ativo = col6.checkbox("Ativo no Orçamento?", value=item['ativo'])
                            
                            if st.form_submit_button("Salvar Alterações"):
                                supabase.table("estoque_filamentos").update({
                                    "material": n_mat, "cor": n_cor, "marca": n_marca,
                                    "peso_restante_g": n_peso, "preco_kg": n_preco, "ativo": n_ativo
                                }).eq("id", item['id']).execute()
                                st.success("Atualizado!")
                                st.rerun()
            else:
                st.info("Nenhum filamento cadastrado.")
                
        with tab2:
            st.subheader("➕ Entrada de Estoque (Média Ponderada)")
            st.info("ℹ️ Se o material já existir, o sistema somará o peso e calculará o novo preço médio automaticamente.")
            
            with st.form("add_stock"):
                c1, c2 = st.columns(2)
                novo_mat = c1.selectbox("Tipo Material", ["PLA", "PETG", "ABS", "ASA", "TPU", "Resina"])
                novo_cor = c2.text_input("Cor (Ex: Azul Navy)").strip() # Remove espaços extras
                novo_marca = c1.text_input("Marca").strip()
                
                c3, c4 = st.columns(2)
                novo_peso_g = c3.number_input("Peso do Carretel (g)", value=1000.0, step=100.0)
                novo_preco_kg = c4.number_input("Preço Pago (R$/Un ou Kg)", value=130.0, step=1.0)
                
                if st.form_submit_button("💾 Atualizar Estoque"):
                    # 1. Busca se já existe esse material no banco
                    res_busca = supabase.table("estoque_filamentos")\
                        .select("*")\
                        .eq("material", novo_mat)\
                        .eq("cor", novo_cor)\
                        .eq("marca", novo_marca)\
                        .execute()
                    
                    if res_busca.data:
                        # --- CENÁRIO: JÁ EXISTE (CÁLCULO DA MÉDIA PONDERADA) ---
                        item_atual = res_busca.data[0]
                        id_atual = item_atual['id']
                        
                        # Dados atuais do banco
                        peso_atual_g = float(item_atual['peso_restante_g'])
                        preco_medio_atual = float(item_atual['preco_kg'])
                        
                        # Cálculo do Valor Total em R$ que você tem hoje
                        valor_total_atual = (peso_atual_g / 1000) * preco_medio_atual
                        
                        # Cálculo do Valor Total que está entrando
                        valor_total_novo = (novo_peso_g / 1000) * novo_preco_kg
                        
                        # Novos Totais
                        peso_final_g = peso_atual_g + novo_peso_g
                        valor_final_total = valor_total_atual + valor_total_novo
                        
                        # Novo Preço Médio por KG
                        if peso_final_g > 0:
                            novo_preco_medio = valor_final_total / (peso_final_g / 1000)
                        else:
                            novo_preco_medio = novo_preco_kg # Segurança contra divisão por zero
                        
                        # Atualiza no Supabase
                        supabase.table("estoque_filamentos").update({
                            "peso_restante_g": peso_final_g,
                            "preco_kg": novo_preco_medio,
                            "ativo": True # Reativa caso estivesse oculto
                        }).eq("id", id_atual).execute()
                        
                        st.success(f"🔄 Estoque atualizado! Novo preço médio: {formatar_moeda(novo_preco_medio)}/kg (Total: {peso_final_g}g)")
                        
                    else:
                        # --- CENÁRIO: NÃO EXISTE (CRIA NOVO) ---
                        supabase.table("estoque_filamentos").insert({
                            "material": novo_mat, 
                            "cor": novo_cor, 
                            "marca": novo_marca,
                            "peso_restante_g": novo_peso_g, 
                            "preco_kg": novo_preco_kg, 
                            "ativo": True
                        }).execute()
                        st.success("✅ Novo material cadastrado com sucesso!")
                    
                    time.sleep(1.5) # Dá tempo de ler a msg
                    st.rerun()

    # --- TELA: CLIENTES ---
    elif menu == "Clientes":
        st.title("👤 Gestão de Clientes")
        aba_lista, aba_novo = st.tabs(["Lista de Clientes", "Novo Cadastro"])
        with aba_lista:
            busca_c = st.text_input("🔍 Buscar cliente por nome...")
            query = supabase.table("clientes").select("*")
            if busca_c: query = query.ilike("nome", f"%{busca_c}%")
            clientes_db = query.order("nome").execute().data
            if clientes_db:
                for c in clientes_db:
                    with st.expander(f"📌 {c['nome']}"):
                        st.write(f"Tel: {c.get('telefone')}")
            else: st.info("Sem clientes.")
        with aba_novo:
            with st.form("novo_cli"):
                n = st.text_input("Nome")
                t = st.text_input("Zap")
                if st.form_submit_button("Salvar") and n:
                    supabase.table("clientes").insert({"nome":n, "telefone":t}).execute()
                    st.rerun()

    # --- TELA: HISTÓRICO ---
    elif menu == "Histórico de Orçamentos":
        st.title("📂 Histórico de Orçamentos")
        try:
            query = supabase.table("orcamentos").select("*, clientes(nome, telefone)").order("criado_em", desc=True).execute()
            if query.data:
                for orc in query.data:
                    if orc.get('clientes'):
                        nome_ex = orc['clientes']['nome']
                        tel_ex = orc['clientes']['telefone']
                    else:
                        nome_ex = orc.get('cliente_nome_manual', 'Consumidor')
                        tel_ex = "Consultar Cadastro" 
                    
                    total_f = formatar_moeda(orc.get('valor_total', 0))
                    
                    with st.expander(f"📄 {orc['criado_em'][:10]} - {nome_ex} | {total_f}"):
                        st.table([{"Item": i['nome'], "Mat": i['material'], "Qtd": i['quantidade']} for i in orc['itens']])
                        
                        c1, c2, c3, c4 = st.columns(4)
                        
                        dados_para_pdf = {"nome": nome_ex, "telefone": tel_ex}
                        pdf_h = gerar_pdf(dados_para_pdf, orc['itens'], "N/A")
                        c1.download_button("📥 PDF", data=pdf_h, file_name=f"Orc_{orc['id']}.pdf")
                        
                        if c3.button("🛒 Virar Pedido", key=f"conv_{orc['id']}", use_container_width=True):
                            supabase.table("pedidos").insert({
                                "orcamento_id": orc['id'],
                                "valor_total": orc['valor_total'],
                                "itens": orc['itens'],
                                "status": "Aguardando Pagamento"
                            }).execute()
                            
                            logs = dar_baixa_estoque(orc['itens'])
                            
                            st.success("Pedido Criado!")
                            if logs:
                                st.write("📉 **Movimentação de Estoque:**")
                                for l in logs: st.write(l)
                            else:
                                st.info("Nenhum item vinculado ao estoque para dar baixa.")
                            
                        if c4.button("🗑️ Excluir", key=f"del_o_{orc['id']}"):
                            supabase.table("orcamentos").delete().eq("id", orc['id']).execute()
                            st.rerun()
            else:
                st.info("Histórico vazio.")
        except Exception as e:
            st.error(f"Erro: {e}")

    # --- TELA: PEDIDOS (PRODUÇÃO) ---
    elif menu == "📦 Pedidos (Produção)":
        st.title("📦 Gestão de Pedidos")
        fluxo = ["Aguardando Pagamento", "Fila de Produção", "Em Produção", "Pronto para Envio", "Entregue"]
        
        res_p = supabase.table("pedidos").select("*, clientes(nome, telefone)").order("criado_em", desc=True).execute()
        
        if res_p.data:
            abas = st.tabs(fluxo)
            for i, status_atual in enumerate(fluxo):
                with abas[i]:
                    pedidos_filtrados = [p for p in res_p.data if p['status'] == status_atual]
                    if not pedidos_filtrados: st.caption("Vazio.")
                    
                    for ped in pedidos_filtrados:
                        with st.container(border=True):
                            # --- 1. CABEÇALHO DO PEDIDO ---
                            cliente_obj = ped.get('clientes') or {}
                            nome_p = cliente_obj.get('nome', "Cliente Avulso")
                            tel_p = cliente_obj.get('telefone', "Sem Contato")
                            
                            st.markdown(f"**Pedido #{ped['id']}** | 👤 {nome_p} | 💰 {formatar_moeda(ped['valor_total'])}")
                            
                            # --- 2. DETALHES (EXPANDER) ---
                            with st.expander("🔎 Ver Detalhes (Itens e Contato)"):
                                st.write(f"📞 Contato: {tel_p}")
                                if ped.get('itens'):
                                    st.table([
                                        {"Item": it['nome'], "Material": it['material'], "Qtd": it['quantidade']} 
                                        for it in ped['itens']
                                    ])
                                else:
                                    st.caption("Sem itens listados.")

                            # --- 3. AÇÕES (BOTÕES) ---
                            col_acoes_1, col_acoes_2 = st.columns([2, 1])

                            with col_acoes_1:
                                if status_atual == "Aguardando Pagamento":
                                    arq = st.file_uploader("Comprovante", key=f"up_{ped['id']}")
                                    if arq and st.button("✅ Confirmar Pagamento", key=f"pay_{ped['id']}", type="primary"):
                                        url = upload_comprovante(ped['id'], arq)
                                        supabase.table("pedidos").update({"status": fluxo[i+1], "comprovante_url": url}).eq("id", ped['id']).execute()
                                        st.rerun()
                                elif i < len(fluxo) - 1:
                                    if st.button(f"➡️ Avançar para: {fluxo[i+1]}", key=f"next_{ped['id']}", type="primary"):
                                        supabase.table("pedidos").update({"status": fluxo[i+1]}).eq("id", ped['id']).execute()
                                        st.rerun()
                                else:
                                    st.success("Pedido Entregue")

                            with col_acoes_2:
                                if st.button("🗑️ Excluir Pedido", key=f"del_ped_{ped['id']}"):
                                    supabase.table("pedidos").delete().eq("id", ped['id']).execute()
                                    st.rerun()