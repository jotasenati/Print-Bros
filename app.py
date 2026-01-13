import streamlit as st
import requests
from fpdf import FPDF
from datetime import datetime, timedelta
import urllib.parse
from supabase import create_client, Client

# --- CONFIGURAÇÕES SUPABASE ---
SUPABASE_URL = "https://heirrnnbgkslndpyyjlx.supabase.co"
SUPABASE_KEY = "sb_secret_Hmuo25aRe-CAEvG852vcFg_qbtkgEE-"

try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error(f"Erro na conexão com Supabase: {e}")

# --- FUNÇÃO BUSCA CEP ---
def buscar_cep(cep):
    cep = str(cep).replace("-", "").replace(".", "").strip()
    if len(cep) == 8:
        try:
            response = requests.get(f"https://viacep.com.br/ws/{cep}/json/")
            if response.status_code == 200:
                dados = response.json()
                if "erro" not in dados:
                    return dados
        except:
            pass
    return None

# --- CONFIGURAÇÕES TÉCNICAS ---
MAQUINAS = {"Bambu Lab A1 Mini": 150, "Anycubic Kobra 3 + ACE Pro": 400}
COR_LARANJA = (244, 161, 130)
COR_CIANO = (148, 211, 204)
TELEFONE_EMPRESA = "11 5194-7240"

def clean(txt):
    return str(txt).encode('latin-1', 'replace').decode('latin-1')

class PrintBrosPDF(FPDF):
    def header(self):
        try:
            self.image('logo.png', 10, 8, 33) 
        except:
            self.set_font("Helvetica", "B", 15)
            self.set_text_color(*COR_LARANJA)
            self.cell(0, 10, "PRINT BROS 3D", ln=True)
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
        self.cell(0, 5, f"Print Bros - Contato: {TELEFONE_EMPRESA}", align='C', ln=True)
        self.cell(0, 5, f"Página {self.page_no()}/{{nb}}", align='C')

def gerar_pdf(dados_cliente, itens, prazo_escolhido):
    pdf = PrintBrosPDF(orientation="P", unit="mm", format="A4")
    pdf.alias_nb_pages()
    pdf.add_page()
    agora = datetime.now()
    data_geracao = agora.strftime("%d/%m/%Y %H:%M")
    data_validade = (agora + timedelta(days=30)).strftime("%d/%m/%Y")
    
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 5, f"Gerado em: {data_geracao}", ln=True, align='R')
    pdf.cell(0, 5, clean(f"Validade: 30 dias ({data_validade})"), ln=True, align='R')
    pdf.ln(5)

    pdf.set_fill_color(245, 245, 245)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 10, " DADOS DO CLIENTE", ln=True, fill=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.ln(2)
    pdf.cell(35, 7, clean("Nome/Empresa:"), border='B')
    pdf.cell(0, 7, f" {clean(dados_cliente.get('nome', 'Consumidor'))}", border='B', ln=True)
    pdf.cell(35, 7, "WhatsApp:", border='B')
    pdf.cell(0, 7, f" {clean(dados_cliente.get('telefone', 'N/A'))}", border='B', ln=True)
    pdf.ln(8)

    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(*COR_LARANJA)
    pdf.set_text_color(255)
    w = [65, 30, 20, 40, 35] 
    pdf.cell(w[0], 10, clean(" Descricao"), 1, 0, 'L', True)
    pdf.cell(w[1], 10, "Material", 1, 0, 'C', True)
    pdf.cell(w[2], 10, "Qtd", 1, 0, 'C', True)
    pdf.cell(w[3], 10, "Prazo Entrega", 1, 0, 'C', True)
    pdf.cell(w[4], 10, "Subtotal (R$)", 1, 1, 'C', True)
    
    pdf.set_text_color(40)
    pdf.set_font("Helvetica", "", 9)
    total_geral = 0
    for item in itens:
        sub = item['preco_final_unitario'] * item['quantidade']
        pdf.cell(w[0], 10, f" {clean(item['nome'])}", 1)
        pdf.cell(w[1], 10, clean(item['material']), 1, 0, 'C')
        pdf.cell(w[2], 10, str(item['quantidade']), 1, 0, 'C')
        pdf.cell(w[3], 10, clean(prazo_escolhido), 1, 0, 'C')
        pdf.cell(w[4], 10, f"{sub:.2f}", 1, 1, 'C')
        total_geral += sub
        
    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_fill_color(*COR_CIANO)
    pdf.cell(sum(w[:4]), 12, clean(" VALOR TOTAL DO PEDIDO "), 1, 0, 'R', True)
    pdf.cell(w[4], 12, f"R$ {total_geral:.2f}", 1, 1, 'C', True)
    return pdf.output(dest='S').encode('latin-1')

# --- APP ---
st.set_page_config(page_title="Print Bros 3D - Gestor", layout="wide")

if 'carrinho' not in st.session_state: st.session_state.carrinho = []
if 'cli_temp' not in st.session_state: st.session_state.cli_temp = {"nome": "Consumidor", "telefone": ""}

menu = st.sidebar.radio("Navegação", ["Calculadora", "Clientes", "Histórico de Orçamentos", "📦 Pedidos (Produção)"])

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
                if escolha != "Selecione...": 
                    st.session_state.cli_temp = opcoes[escolha]
                    st.success(f"Selecionado: {escolha}")
    else:
        c1, c2 = st.columns(2)
        st.session_state.cli_temp['nome'] = c1.text_input("Nome do Cliente", value=st.session_state.cli_temp.get('nome', 'Consumidor'))
        st.session_state.cli_temp['telefone'] = c2.text_input("WhatsApp do Cliente", value=st.session_state.cli_temp.get('telefone', ''))

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
        
        st.divider()
        col_v, col_m, col_q = st.columns([2, 1, 1])
        v_final_manual = col_v.number_input("VALOR FINAL MANUAL (Unitário R$)", min_value=0.0, step=1.0)
        margem = col_m.slider("Margem % (Se Valor Final for 0)", 0, 500, 100)
        qtd_p = col_q.number_input("Quantidade", min_value=1, value=1)
        
        if v_final_manual > 0:
            venda_un = float(v_final_manual)
            metodo = "Manual"
        else:
            custo_base = ((MAQUINAS[m_p]/1000) * t_h * 0.73) + ((pr_kg/1000) * p_g) + 15.0
            venda_un = round(custo_base * (1 + margem/100), 2)
            metodo = f"Automático ({margem}%)"
            
        st.info(f"Unitário: R$ {venda_un:.2f} | Método: {metodo}")
        
        if st.button("➕ Adicionar ao Carrinho"):
            if n_p:
                st.session_state.carrinho.append({
                    "id": datetime.now().timestamp(),
                    "nome": n_p, "maquina": m_p, "material": mat_p, 
                    "preco_final_unitario": venda_un, "quantidade": int(qtd_p)
                })
                st.rerun()

    if st.session_state.carrinho:
        st.divider()
        st.subheader("📋 Resumo")
        for idx, item in enumerate(st.session_state.carrinho):
            col1, col2, col3, col4 = st.columns([3, 1, 1, 0.5])
            col1.write(f"**{item['nome']}**")
            col2.write(f"{item['quantidade']}x R$ {item['preco_final_unitario']:.2f}")
            col3.write(f"R$ {item['preco_final_unitario'] * item['quantidade']:.2f}")
            if col4.button("🗑️", key=f"del_{item['id']}"):
                st.session_state.carrinho.pop(idx)
                st.rerun()

        prazo_data = st.date_input("📅 Prazo de Entrega", value=datetime.now() + timedelta(days=3))
        total_final = sum(i['preco_final_unitario'] * i['quantidade'] for i in st.session_state.carrinho)
        st.markdown(f"### Total: R$ {total_final:.2f}")
        
        c1, c2, c3 = st.columns(3)
        pdf_bytes = gerar_pdf(st.session_state.cli_temp, st.session_state.carrinho, prazo_data.strftime("%d/%m/%Y"))
        c1.download_button("📥 Baixar PDF", data=pdf_bytes, file_name=f"Orcamento_{st.session_state.cli_temp['nome']}.pdf")
        
        if c2.button("💾 Salvar Histórico"):
            with st.status("Processando salvamento...", expanded=True) as status:
                try:
                    nome_cli = st.session_state.cli_temp.get('nome')
                    tel_cli = st.session_state.cli_temp.get('telefone')
                    id_cliente_final = st.session_state.cli_temp.get('id')

                    if not nome_cli or nome_cli == "Consumidor":
                        st.error("Por favor, informe o nome do cliente antes de salvar.")
                        st.stop()

                    status.write("🔍 Verificando cliente no banco...")
                    res_c = supabase.table("clientes").select("id").eq("nome", nome_cli).execute()
                    
                    if res_c.data:
                        id_cliente_final = res_c.data[0]['id']
                        status.write(f"✅ Cliente encontrado (ID: {id_cliente_final})")
                    else:
                        status.write("🆕 Cliente novo! Criando cadastro...")
                        new_c = supabase.table("clientes").insert({"nome": nome_cli, "telefone": tel_cli}).execute()
                        if new_c.data:
                            id_cliente_final = new_c.data[0]['id']
                            status.write(f"✅ Cliente cadastrado!")

                    status.write("💾 Gravando orçamento...")
                    dados_orc = {
                        "valor_total": total_final, 
                        "itens": st.session_state.carrinho,
                        "prazo_entrega": prazo_data.strftime("%d/%m/%Y"),
                        "cliente_nome_manual": nome_cli,
                        "cliente_tel_manual": tel_cli,
                        "cliente_id": id_cliente_final
                    }
                    
                    res_o = supabase.table("orcamentos").insert(dados_orc).execute()
                    
                    if res_o.data:
                        status.update(label="✅ Salvo com sucesso!", state="complete", expanded=False)
                        st.success(f"Orçamento gravado!")
                    else:
                        st.error("Erro ao gravar orçamento.")

                except Exception as e:
                    st.error(f"Erro: {e}")

        if c3.button("🗑️ Limpar Tudo"):
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
                        st.rerun()
        else:
            st.info("Nenhum cliente encontrado.")

    with aba_novo:
        st.subheader("➕ Novo Cadastro")
        c_cep = st.text_input("CEP (Preenchimento automático)")
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
        query = supabase.table("orcamentos").select("*, clientes(nome, telefone)").order("criado_em", desc=True).execute()
        if query.data:
            for orc in query.data:
                nome_ex = orc['clientes']['nome'] if orc.get('clientes') else orc.get('cliente_nome_manual', 'N/A')
                with st.expander(f"📄 {orc['criado_em'][:10]} - {nome_ex} | R$ {orc.get('valor_total', 0):.2f}"):
                    itens_pdf = []
                    for item in orc.get('itens', []):
                        p = item.get('preco_final_unitario') or 0
                        itens_pdf.append({"nome": item.get('nome'), "material": item.get('material', 'PLA'), "preco_final_unitario": p, "quantidade": item.get('quantidade', 1)})
                    
                    st.table(itens_pdf)
                    
                    c1, c2, c3 = st.columns(3)
                    
                    # GERAR PDF
                    pdf_h = gerar_pdf({"nome": nome_ex, "telefone": orc.get('cliente_tel_manual')}, itens_pdf, orc.get('prazo_entrega', 'N/A'))
                    c1.download_button("📥 PDF", data=pdf_h, file_name=f"Orcamento_{orc['id']}.pdf", key=f"h_{orc['id']}")
                    
                    # CONVERTER EM PEDIDO
                    if c2.button("🛒 Converter em Pedido", key=f"conv_{orc['id']}", type="primary"):
                        res_p = supabase.table("pedidos").insert({
                            "orcamento_id": orc['id'],
                            "cliente_id": orc.get('cliente_id'),
                            "valor_total": orc['valor_total'],
                            "itens": orc['itens'],
                            "status": "Aguardando Pagamento"
                        }).execute()
                        if res_p.data:
                            st.success("Pedido gerado com sucesso!")
                    
                    # EXCLUIR
                    if c3.button("🗑️ Excluir", key=f"del_o_{orc['id']}"):
                        supabase.table("orcamentos").delete().eq("id", orc['id']).execute()
                        st.rerun()
        else:
            st.info("Nenhum orçamento no histórico.")
    except Exception as e:
        st.error(f"Erro ao carregar histórico: {e}")

# --- TELA: PEDIDOS (FLUXO DE PRODUÇÃO) ---
elif menu == "📦 Pedidos (Produção)":
    st.title("📦 Gestão de Pedidos")
    
    res_p = supabase.table("pedidos").select("*, clientes(nome, telefone)").order("criado_em", desc=True).execute()
    
    if res_p.data:
        status_opcoes = ["Aguardando Pagamento", "Em Produção", "Pronto para Envio", "Finalizado"]
        abas = st.tabs(status_opcoes)
        
        for i, status_nome in enumerate(status_opcoes):
            with abas[i]:
                pedidos_filtrados = [p for p in res_p.data if p['status'] == status_nome]
                if not pedidos_filtrados:
                    st.caption(f"Sem pedidos em {status_nome.lower()}.")
                
                for ped in pedidos_filtrados:
                    with st.container(border=True):
                        nome_p = ped['clientes']['nome'] if ped.get('clientes') else "Cliente Avulso"
                        c1, c2, c3 = st.columns([2, 1, 1])
                        
                        c1.markdown(f"**Pedido #{ped['id']}** - {nome_p}")
                        c1.caption(f"Valor: R$ {ped['valor_total']:.2f}")
                        
                        novo_status = c2.selectbox(
                            "Status", 
                            status_opcoes, 
                            index=status_opcoes.index(ped['status']),
                            key=f"st_change_{ped['id']}"
                        )
                        
                        if novo_status != ped['status']:
                            supabase.table("pedidos").update({"status": novo_status}).eq("id", ped['id']).execute()
                            st.rerun()
                            
                        if c3.button("🔍 Detalhes", key=f"det_ped_{ped['id']}"):
                            st.write("**Resumo da Produção:**")
                            st.table(ped['itens'])
    else:
        st.info("Converta um orçamento no histórico para iniciar um pedido.")