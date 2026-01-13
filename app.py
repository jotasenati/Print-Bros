import streamlit as st
import requests
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

# --- SISTEMA DE AUTENTICAÇÃO ---
def autenticar():
    if "autenticado" not in st.session_state:
        st.session_state["autenticado"] = False

    if not st.session_state["autenticado"]:
        st.markdown("### 🔐 PRINT BROS - Login")
        with st.form("login_form"):
            user_input = st.text_input("Usuário")
            pass_input = st.text_input("Senha", type="password")
            if st.form_submit_button("Acessar Sistema"):
                res = supabase.table("usuarios").select("*").eq("username", user_input).eq("password", pass_input).execute()
                if res.data:
                    st.session_state["autenticado"] = True
                    st.session_state["usuario_nome"] = res.data[0]['nome']
                    st.rerun()
                else:
                    st.error("Usuário ou senha incorretos.")
        return False
    return True

# --- FUNÇÕES AUXILIARES ---
def formatar_moeda(valor):
    """Transforma um número em string formato BRL R$ 0,00"""
    try:
        return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return "R$ 0,00"

def buscar_cep(cep):
    cep = str(cep).replace("-", "").replace(".", "").strip()
    if len(cep) == 8:
        try:
            response = requests.get(f"https://viacep.com.br/ws/{cep}/json/")
            if response.status_code == 200:
                dados = response.json()
                return dados if "erro" not in dados else None
        except: pass
    return None

def upload_comprovante(pedido_id, arquivo):
    try:
        file_path = f"comprovante_{pedido_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
        supabase.storage.from_("comprovantes").upload(file_path, arquivo.read(), {"content-type": arquivo.type})
        return supabase.storage.from_("comprovantes").get_public_url(file_path)
    except Exception as e:
        st.error(f"Erro no upload: {e}")
        return None

# --- CONFIGURAÇÕES TÉCNICAS E PDF ---
MAQUINAS = {"Bambu Lab A1 Mini": 150, "Anycubic Kobra 3 + ACE Pro": 400}
COR_LARANJA = (244, 161, 130)
COR_CIANO = (148, 211, 204)
TELEFONE_EMPRESA = "11 5194-7240"

def clean(txt):
    return str(txt).encode('latin-1', 'replace').decode('latin-1')

# --- LAYOUT DE IMPRESSÃO ---
class PrintBrosPDF(FPDF):
    def header(self):
        try:
            self.image('logo.png', 10, 8, 33) 
        except:
            self.set_font("Helvetica", "B", 15)
            self.set_text_color(*COR_LARANJA)
            self.cell(0, 10, "PRINT BROS", ln=True)
        
        self.set_xy(100, 15)
        self.set_font("Helvetica", "B", 16)
        self.set_text_color(60, 60, 60)
        self.cell(100, 10, clean("ORÇAMENTO DE SERVIÇOS"), align='R', ln=True)
        self.ln(20)

    def footer(self):
        self.set_y(-25)
        self.set_draw_color(*COR_CIANO)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(5)
        self.set_font("Helvetica", "I", 9)
        self.set_text_color(100, 100, 100)
        resp = st.session_state.get("usuario_nome", "Não identificado")
        self.cell(0, 5, clean(f"Responsável: {resp} | Contato: {TELEFONE_EMPRESA}"), align='C', ln=True)
        self.cell(0, 5, f"Pagina {self.page_no()}/{{nb}}", align='C')

class PrintBrosPDF(FPDF):
    def header(self):
        # Barra decorativa no topo (Identidade Visual)
        self.set_fill_color(*COR_LARANJA)
        self.rect(0, 0, 210, 15, 'F')
        
        # Espaço para Logo
        try:
            # Tente ajustar o caminho se necessário. Ex: 'assets/logo.png'
            self.image('logo.png', 12, 20, 35) 
        except:
            # Caso não encontre a logo, desenha um "Selo" de marca
            self.set_xy(10, 20)
            self.set_font("Helvetica", "B", 18)
            self.set_text_color(*COR_LARANJA)
            self.cell(50, 10, "PRINT BROS", ln=False)
        
        # Título do Documento à Direita
        self.set_xy(110, 20)
        self.set_font("Helvetica", "B", 22)
        self.set_text_color(40, 40, 40)
        self.cell(90, 15, clean("ORÇAMENTO"), align='R', ln=True)
        
        # Linha fina decorativa
        self.set_draw_color(*COR_CIANO)
        self.set_line_width(0.5)
        self.line(10, 42, 200, 42)
        self.ln(15)

    def footer(self):
        self.set_y(-30)
        # Linha de rodapé
        self.set_draw_color(200, 200, 200)
        self.line(10, self.get_y(), 200, self.get_y())
        
        self.ln(5)
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(60, 60, 60)
        
        # Nome do Responsável com destaque
        resp = st.session_state.get("usuario_nome", "Departamento Comercial")
        self.cell(0, 5, clean(f"Responsável: {resp.upper()}"), align='C', ln=True)
        
        self.set_font("Helvetica", "", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 5, clean(f"PRINT BROS - Contato: {TELEFONE_EMPRESA} | Página {self.page_no()}/{{nb}}"), align='C')

def gerar_pdf(dados_cliente, itens, prazo):
    pdf = PrintBrosPDF()
    pdf.alias_nb_pages()
    pdf.add_page()
    
    # --- BOX DADOS DO CLIENTE ---
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

    # --- TABELA DE ITENS (DESIGN PROFISSIONAL) ---
    # Cabeçalho
    pdf.set_fill_color(60, 60, 60) # Cinza escuro para o cabeçalho
    pdf.set_text_color(255, 255, 255) # Texto branco
    pdf.set_font("Helvetica", "B", 10)
    
    pdf.cell(95, 10, clean(" DESCRIÇÃO DO SERVIÇO / PEÇA"), border=0, fill=True)
    pdf.cell(35, 10, clean("MATERIAL"), border=0, fill=True, align='C')
    pdf.cell(20, 10, clean("QTD"), border=0, fill=True, align='C')
    pdf.cell(40, 10, clean("TOTAL "), border=0, fill=True, align='R', ln=True)

    # Corpo da Tabela
    pdf.set_text_color(50, 50, 50)
    pdf.set_font("Helvetica", "", 10)
    
    total_geral = 0
    zebra = False # Para fazer linhas alternadas
    
    for item in itens:
        v_unit = float(item.get('preco_final_unitario', 0))
        qtd = int(item.get('quantidade', 1))
        subtotal = v_unit * qtd
        total_geral += subtotal
        
        # Cor de fundo alternada (Zebrada)
        bg_color = (245, 245, 245) if zebra else (255, 255, 255)
        pdf.set_fill_color(*bg_color)
        
        pdf.cell(95, 9, clean(f" {item['nome']}"), border='B', fill=True)
        pdf.cell(35, 9, clean(item['material']), border='B', fill=True, align='C')
        pdf.cell(20, 9, str(qtd), border='B', fill=True, align='C')
        pdf.cell(40, 9, formatar_moeda(subtotal) + " ", border='B', fill=True, align='R', ln=True)
        
        zebra = not zebra

    # --- RESUMO FINANCEIRO ---
    pdf.ln(10)
    # Caixa de total à direita
    pdf.set_x(130)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_fill_color(*COR_LARANJA)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(70, 12, clean(f" TOTAL GERAL: {formatar_moeda(total_geral)}"), align='C', fill=True)
    
    # Notas Rodapé do documento
    pdf.set_xy(10, pdf.get_y() + 5)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(100, 100, 100)
    pdf.multi_cell(110, 4, clean("Validade deste orçamento: 7 dias.\nPrazo de produção estimado após aprovação do pagamento."))

    return pdf.output(dest='S').encode('latin-1')
# --- INÍCIO DO APP ---
if autenticar():
    st.set_page_config(page_title="PRINT BROS - Gestor", layout="wide")
    
    if 'carrinho' not in st.session_state: st.session_state.carrinho = []
    if 'cli_temp' not in st.session_state: st.session_state.cli_temp = {"nome": "Consumidor", "telefone": ""}

    menu = st.sidebar.radio("Navegação", ["Calculadora", "Clientes", "Histórico de Orçamentos", "📦 Pedidos (Produção)"])
    if st.sidebar.button("Sair"):
        st.session_state["autenticado"] = False
        st.rerun()

    # --- TELA: CALCULADORA ---
    if menu == "Calculadora":
        st.title("🖨️ Calculadora & Orçamento")
        col_a, col_b = st.columns([2, 1])
        with col_a:
            tipo_orc = st.radio("Tipo de Orçamento:", ["Rápido (Sem cadastro)", "Profissional (Banco)"], horizontal=True)
        
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
            st.subheader("🛠️ Adicionar Peça")
            c1, c2, c3 = st.columns(3)
            n_p = c1.text_input("Nome da Peça")
            m_p = c2.selectbox("Máquina", list(MAQUINAS.keys()))
            mat_p = c3.selectbox("Material", ["PLA", "PETG", "ABS", "Resina"])
            
            c4, c5, c6 = st.columns(3)
            p_g = c4.number_input("Gramas", min_value=0.0)
            t_h = c5.number_input("Horas", min_value=0.0)
            pr_kg = c6.number_input("R$ KG Material", value=130.0)
            
            v_final_manual = st.number_input("VALOR FINAL MANUAL (Unitário R$)", min_value=0.0)
            
            if st.button("➕ Adicionar ao Carrinho"):
                venda_un = v_final_manual if v_final_manual > 0 else round(((MAQUINAS[m_p]/1000)*t_h*0.73) + ((pr_kg/1000)*p_g) + 15.0, 2)
                st.session_state.carrinho.append({"id": datetime.now().timestamp(), "nome": n_p, "maquina": m_p, "material": mat_p, "preco_final_unitario": venda_un, "quantidade": 1})
                st.rerun()

        if st.session_state.carrinho:
            st.subheader("📋 Resumo")
            total = sum(item['preco_final_unitario'] * item['quantidade'] for item in st.session_state.carrinho)
            for i, item in enumerate(st.session_state.carrinho):
                # Tratamento de valor no resumo do carrinho
                st.write(f"• {item['nome']} - {formatar_moeda(item['preco_final_unitario'])}")
            
            st.markdown(f"### Total: {formatar_moeda(total)}")

            if st.button("💾 Salvar Orçamento"):
                dados = {
                    "valor_total": total, 
                    "itens": st.session_state.carrinho, 
                    "cliente_nome_manual": st.session_state.cli_temp['nome'], 
                    "cliente_id": st.session_state.cli_temp.get('id'),
                    "criado_por": st.session_state.usuario_nome
                }
                supabase.table("orcamentos").insert(dados).execute()
                st.success("Salvo com sucesso!")
                st.session_state.carrinho = []
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
                    with st.expander(f"📌 {c['nome']} | 📱 {c.get('telefone', 'N/A')}"):
                        c_cep_edit = st.text_input("CEP", value=c.get('cep', ''), key=f"cep_e_{c['id']}")
                        info_cep_e = buscar_cep(c_cep_edit) if c_cep_edit else None
                        
                        with st.form(key=f"edit_{c['id']}"):
                            col1, col2 = st.columns(2)
                            n_nome = col1.text_input("Nome/Empresa", value=c['nome'])
                            n_tel = col2.text_input("WhatsApp", value=c.get('telefone', ''))
                            
                            rua_v = info_cep_e['logradouro'] if info_cep_e else c.get('endereco', '')
                            bairro_v = info_cep_e['bairro'] if info_cep_e else c.get('bairro', '')
                            cidade_v = info_cep_e['localidade'] if info_cep_e else c.get('cidade', '')
                            
                            n_end = col1.text_input("Endereço", value=rua_v)
                            n_bairro = col2.text_input("Bairro", value=bairro_v)
                            n_cidade = col1.text_input("Cidade", value=cidade_v)
                            n_email = col2.text_input("E-mail", value=c.get('email', ''))

                            if st.form_submit_button("💾 Salvar Alterações"):
                                supabase.table("clientes").update({
                                    "nome": n_nome, "telefone": n_tel, "cep": c_cep_edit,
                                    "endereco": n_end, "bairro": n_bairro, "cidade": n_cidade, "email": n_email
                                }).eq("id", c['id']).execute()
                                st.success("Atualizado!")
                                st.rerun()
                        
                        if st.button(f"🗑️ Excluir Cliente", key=f"del_c_{c['id']}"):
                            supabase.table("clientes").delete().eq("id", c['id']).execute()
                            st.success("Cliente removido!")
                            st.rerun()
            else:
                st.info("Nenhum cliente encontrado.")

        with aba_novo:
            st.subheader("➕ Novo Cadastro")
            c_cep = st.text_input("CEP (Preenchimento automático)", key="novo_cep")
            info_cep = buscar_cep(c_cep) if c_cep else None
            
            with st.form("novo_cli", clear_on_submit=True):
                col1, col2 = st.columns(2)
                v_nome = col1.text_input("Nome/Empresa*")
                v_tel = col2.text_input("WhatsApp*")
                v_end = col1.text_input("Rua", value=info_cep['logradouro'] if info_cep else "")
                v_bairro = col2.text_input("Bairro", value=info_cep['bairro'] if info_cep else "")
                v_cidade = col1.text_input("Cidade", value=info_cep['localidade'] if info_cep else "")
                v_email = col2.text_input("E-mail")
                
                if st.form_submit_button("Cadastrar"):
                    if v_nome and v_tel:
                        supabase.table("clientes").insert({
                            "nome": v_nome, "telefone": v_tel, "cep": c_cep,
                            "endereco": v_end, "bairro": v_bairro, "cidade": v_cidade, "email": v_email
                        }).execute()
                        st.success("Cliente cadastrado!")
                        st.rerun()

    # --- TELA: HISTÓRICO ---
    elif menu == "Histórico de Orçamentos":
        st.title("📂 Histórico de Orçamentos")
        try:
            # A query já traz os dados do cliente vinculado
            query = supabase.table("orcamentos").select("*, clientes(nome, telefone)").order("criado_em", desc=True).execute()
            
            if query.data:
                for orc in query.data:
                    # 1. Extração do Nome e Telefone
                    if orc.get('clientes'):
                        nome_ex = orc['clientes']['nome']
                        tel_ex = orc['clientes']['telefone']
                    else:
                        nome_ex = orc.get('cliente_nome_manual', 'Consumidor')
                        tel_ex = "Consultar Cadastro" 

                    usuario_vendedor = orc.get('criado_por', 'Sistema')
                    total_f = formatar_moeda(orc.get('valor_total', 0))
                    
                    with st.expander(f"📄 {orc['criado_em'][:10]} - {nome_ex} (Por: {usuario_vendedor}) | {total_f}"):
                        st.info(f"**Vendedor Responsável:** {usuario_vendedor}")
                        
                        itens_para_tabela = []
                        itens_orc = orc.get('itens', [])
                        
                        # --- PREPARAÇÃO PARA CONCORDÂNCIA E LISTAGEM ---
                        nomes_produtos = []
                        total_unidades = 0
                        
                        for item in itens_orc:
                            p = item.get('preco_final_unitario') or 0
                            qtd = int(item.get('quantidade', 1))
                            total_unidades += qtd
                            nomes_produtos.append(f"{qtd}x {item['nome']}")
                            
                            itens_para_tabela.append({
                                "Peça": item.get('nome'), 
                                "Material": item.get('material', 'PLA'), 
                                "Valor Unit.": formatar_moeda(p), 
                                "Quantidade": qtd
                            })
                        
                        st.table(itens_para_tabela)
                        
                        c1, c2, c3, c4 = st.columns(4)
                        
                        # --- DADOS PARA O PDF ---
                        dados_para_pdf = {
                            "nome": nome_ex, 
                            "vendedor": usuario_vendedor,
                            "telefone": tel_ex 
                        }
                        pdf_h = gerar_pdf(dados_para_pdf, itens_orc, "N/A")
                        
                        # Coluna 1: Baixar
                        c1.download_button("📥 Baixar PDF", data=pdf_h, file_name=f"Orcamento_{orc['id']}.pdf", key=f"pdf_{orc['id']}")
                        
                        # Coluna 2: WhatsApp com Concordância Verbal
                        if tel_ex and tel_ex != "Consultar Cadastro":
                            # Lógica de concordância
                            lista_produtos_str = ", ".join(nomes_produtos)
                            termo_unidade = "unidade" if total_unidades == 1 else "unidades"
                            
                            # Limpar o número
                            tel_limpo = "".join(filter(str.isdigit, tel_ex))
                            if not tel_limpo.startswith("55"): tel_limpo = "55" + tel_limpo
                            
                            # Mensagem Personalizada
                            msg = (
                                f"Olá {nome_ex}, segue o seu orçamento para o(s) *{lista_produtos_str}* "
                                f"({total_unidades} {termo_unidade}) no total de *{total_f}*. "
                                f"Vou encaminhar em seguida o PDF com os detalhes do pedido."
                            )
                            
                            import urllib.parse
                            msg_url = urllib.parse.quote(msg)
                            link_wa = f"https://wa.me/{tel_limpo}?text={msg_url}"
                            
                            c2.markdown(f'''
                                <a href="{link_wa}" target="_blank">
                                    <button style="width:100%; height:38px; background-color:#25D366; color:white; border:none; border-radius:5px; cursor:pointer; font-weight:bold;">
                                        🟢 WhatsApp
                                    </button>
                                </a>
                            ''', unsafe_allow_html=True)
                        else:
                            c2.warning("Sem Número")

                        # Coluna 3: Converter em Pedido
                        if c3.button("🛒 Pedido", key=f"conv_{orc['id']}", use_container_width=True):
                            supabase.table("pedidos").insert({
                                "orcamento_id": orc['id'],
                                "valor_total": orc['valor_total'],
                                "itens": orc['itens'],
                                "status": "Aguardando Pagamento"
                            }).execute()
                            st.success("Convertido!")
                        
                        # Coluna 4: Excluir
                        if c4.button("🗑️ Excluir", key=f"del_o_{orc['id']}", use_container_width=True):
                            supabase.table("orcamentos").delete().eq("id", orc['id']).execute()
                            st.rerun()
            else:
                st.info("Nenhum orçamento encontrado.")
        except Exception as e:
            st.error(f"Erro ao carregar histórico: {e}")

    # --- TELA: PEDIDOS (PRODUÇÃO) ---
    elif menu == "📦 Pedidos (Produção)":
        st.title("📦 Gestão de Pedidos") # Certifique-se de que há 4 ou 8 espaços aqui
        fluxo = ["Aguardando Pagamento", "Fila de Produção", "Em Produção", "Pronto para Envio", "Entregue"]
        
        try:
            res_p = supabase.table("pedidos").select("*, clientes(nome, telefone)").order("criado_em", desc=True).execute()
            
            if res_p.data:
                abas = st.tabs(fluxo)
                for i, status_atual in enumerate(fluxo):
                    with abas[i]:
                        pedidos_filtrados = [p for p in res_p.data if p['status'] == status_atual]
                        if not pedidos_filtrados:
                            st.caption(f"Nenhum pedido em '{status_atual}'.")
                        
                        for ped in pedidos_filtrados:
                            with st.container(border=True):
                                # Extração segura de dados
                                cliente_obj = ped.get('clientes') or {}
                                nome_p = cliente_obj.get('nome', "Cliente Avulso")
                                tel_p = cliente_obj.get('telefone', "")
                                
                                c1, c2 = st.columns([3, 1])
                                c1.markdown(f"### Pedido #{ped['id']} - {nome_p}")
                                c1.write(f"**Valor Total:** {formatar_moeda(ped['valor_total'])}")
                                
                                # Lista de produtos para a mensagem
                                itens_list = [f"{it['quantidade']}x {it['nome']}" for it in ped['itens']]
                                produtos_str = ", ".join(itens_list)

                                if status_atual == "Aguardando Pagamento":
                                    st.warning("Aguardando upload do comprovante para iniciar produção.")
                                    arq = st.file_uploader("Anexar Comprovante", type=['pdf', 'png', 'jpg', 'jpeg'], key=f"file_{ped['id']}")
                                    if arq:
                                        if st.button("✅ Confirmar Pagamento", key=f"btn_pay_{ped['id']}", type="primary"):
                                            url = upload_comprovante(ped['id'], arq)
                                            if url:
                                                supabase.table("pedidos").update({"status": fluxo[i+1], "comprovante_url": url}).eq("id", ped['id']).execute()
                                                st.rerun()

                                elif i < len(fluxo) - 1:
                                    proximo_status = fluxo[i+1]
                                    col_btn1, col_btn2 = st.columns(2)
                                    
                                    if ped.get("comprovante_url"):
                                        col_btn1.link_button("📄 Ver Comprovante", ped["comprovante_url"], use_container_width=True)
                                    
                                    if col_btn2.button(f"➡️ Ir para: {proximo_status}", key=f"next_{ped['id']}", use_container_width=True, type="primary"):
                                        # 1. Atualiza no Banco
                                        supabase.table("pedidos").update({"status": proximo_status}).eq("id", ped['id']).execute()
                                        
                                        # 2. Notificação via Link
                                        if tel_p:
                                            tel_limpo = "".join(filter(str.isdigit, tel_p))
                                            if not tel_limpo.startswith("55"): tel_limpo = "55" + tel_limpo
                                            
                                            msg = (
                                                f"Olá *{nome_p}*! Atualizamos o status do seu pedido na *Print Bros 3D*.\n\n"
                                                f"📦 *Pedido:* {produtos_str}\n"
                                                f"📍 *Novo Status:* _{proximo_status}_\n\n"
                                                f"Estamos cuidando de tudo!"
                                            )
                                            import urllib.parse
                                            link_wa = f"https://wa.me/{tel_limpo}?text={urllib.parse.quote(msg)}"
                                            st.success(f"Status atualizado! [Clique aqui para avisar no WhatsApp]({link_wa})")
                                        
                                        st.rerun()
                                else:
                                    st.success("✅ Pedido Entregue e Finalizado.")

                                with st.expander("🔍 Ver Itens"):
                                    st.table(ped['itens'])
            else:
                st.info("Nenhum pedido encontrado.")
        except Exception as e:
            st.error(f"Erro ao carregar pedidos: {e}")