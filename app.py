import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import streamlit as st
import os
from core.parser import BatchParser
from core.formalizer import llm_translate_to_z3
from core.verifier import MathematicalVerifier
from utils.cache_manager import CacheManager

st.set_page_config(page_title="Math Proof Checker", layout="wide")

# --- Inicialización de Estado y Caché ---
cache_manager = CacheManager()

if 'pdf_bytes' not in st.session_state:
    st.session_state.pdf_bytes = None
if 'total_pages' not in st.session_state:
    st.session_state.total_pages = 0
if 'total_batches' not in st.session_state:
    st.session_state.total_batches = 0
if 'current_batch' not in st.session_state:
    st.session_state.current_batch = 0
if 'batch_size' not in st.session_state:
    st.session_state.batch_size = 10

# --- Interfaz ---
st.title("🧮 Verificador Formal de Demostraciones (Por Lotes)")
st.markdown("Sistema de verificación matemática rigurosa con procesamiento optimizado para evitar saturación.")

with st.sidebar:
    st.header("⚙️ Configuración")
    st.session_state.batch_size = st.slider("Páginas por lote", 5, 20, 10)
    st.markdown("---")
    if st.button("🗑️ Limpiar Caché"):
        import shutil
        if os.path.exists(".streamlit_cache"):
            shutil.rmtree(".streamlit_cache")
            os.makedirs(".streamlit_cache")
        st.success("Caché eliminada")

# --- Carga de Archivo ---
uploaded_file = st.file_uploader("Sube tu documento (PDF)", type=["pdf"])

if uploaded_file is not None:
    # Solo procesamos la metadata del PDF una vez
    if st.session_state.pdf_bytes is None or st.session_state.pdf_bytes != uploaded_file.getvalue():
        st.session_state.pdf_bytes = uploaded_file.getvalue()
        
        import fitz
        doc = fitz.open(stream=st.session_state.pdf_bytes, filetype="pdf")
        st.session_state.total_pages = len(doc)
        doc.close()
        
        parser = BatchParser(batch_size=st.session_state.batch_size)
        st.session_state.total_batches = parser.get_total_batches(st.session_state.total_pages)
        st.session_state.current_batch = 0 # Reiniciar al primer lote
        
        st.success(f"✅ Documento cargado: {st.session_state.total_pages} páginas en {st.session_state.total_batches} lotes.")

    # --- Navegación por Lotes ---
    if st.session_state.total_batches > 0:
        st.markdown("---")
        col1, col2, col3 = st.columns([1, 2, 1])
        
        with col1:
            if st.button("⬅️ Anterior", disabled=st.session_state.current_batch == 0):
                st.session_state.current_batch -= 1
                st.rerun()
        
        with col2:
            batch_num = st.session_state.current_batch
            parser = BatchParser(batch_size=st.session_state.batch_size)
            start_p, end_p = parser.get_page_range(batch_num, st.session_state.total_pages)
            
            st.session_state.current_batch = st.selectbox(
                "Ir al lote:",
                options=range(st.session_state.total_batches),
                index=batch_num,
                format_func=lambda x: f"Lote {x+1} (Págs. {parser.get_page_range(x, st.session_state.total_pages)[0]+1}-{parser.get_page_range(x, st.session_state.total_pages)[1]})"
            )
            # Si el usuario cambia el selectbox, recargamos
            if st.session_state.current_batch != batch_num:
                st.rerun()
        
        with col3:
            if st.button("Siguiente ➡️", disabled=st.session_state.current_batch >= st.session_state.total_batches - 1):
                st.session_state.current_batch += 1
                st.rerun()

        # Barra de progreso general
        progress = (st.session_state.current_batch + 1) / st.session_state.total_batches
        st.progress(progress, text=f"Progreso general: Lote {st.session_state.current_batch + 1} de {st.session_state.total_batches}")

        # --- Procesamiento del Lote Actual ---
        current_batch = st.session_state.current_batch
        cache_key = f"batch_{current_batch}" # Simplificado para session state + disk cache
        
        # Intentar obtener de caché en disco primero
        cached_result = cache_manager.get_cached_batch(
            st.session_state.pdf_bytes, 
            current_batch, 
            st.session_state.batch_size
        )

        if cached_result is None:
            with st.spinner(f"⏳ Procesando y verificando formalmente el Lote {current_batch + 1}..."):
                parser = BatchParser(batch_size=st.session_state.batch_size)
                batch_data = parser.extract_batch(st.session_state.pdf_bytes, current_batch, st.session_state.total_pages)
                
                verifier = MathematicalVerifier()
                verification_results = []
                
                for page_data in batch_data["pages"]:
                    page_results = []
                    # 1. Formalizar
                    formal_claims = llm_translate_to_z3(page_data["claims"])
                    
                    # 2. Verificar
                    for claim in formal_claims:
                        res = verifier.check_algebraic_identity(claim["z3_code"], page_data["page_number"])
                        res["original_claim"] = claim["original"]
                        page_results.append(res)
                        
                    verification_results.append({
                        "page_number": page_data["page_number"],
                        "text": page_data["text"],
                        "results": page_results
                    })
                
                # Guardar en caché en disco
                cache_manager.save_batch_to_cache(
                    st.session_state.pdf_bytes, 
                    current_batch, 
                    st.session_state.batch_size, 
                    verification_results
                )
                final_results = verification_results
        else:
            final_results = cached_result

        # --- Visualización de Resultados ---
        st.markdown(f"### 📊 Resultados del Lote {current_batch + 1}")
        
        for page_res in final_results:
            with st.expander(f"📄 Página {page_res['page_number']}", expanded=False):
                st.markdown("**Texto extraído:**")
                st.text_area("", value=page_res["text"], height=100, disabled=True, key=f"text_{page_res['page_number']}")
                
                st.markdown("**Verificación Formal:**")
                for res in page_res["results"]:
                    if res["status"] == "VALID":
                        st.success(f"✅ **VÁLIDO**: {res['message']}")
                        st.markdown(f"*Afirmación:* `{res['original_claim']}`")
                    elif res["status"] == "ERROR":
                        st.error(f"❌ **ERROR DETECTADO**: {res['message']}")
                        st.markdown(f"*Afirmación:* `{res['original_claim']}`")
                        st.markdown(f"**Contraejemplo Z3:** `{res['counterexample']}`")
                    else:
                        st.warning(f"⚠️ **{res['status']}**: {res['message']}")
                        st.markdown(f"*Afirmación:* `{res['original_claim']}`")

        # --- Botón de Procesamiento Masivo ---
        st.markdown("---")
        remaining = st.session_state.total_batches - current_batch - 1
        if remaining > 0:
            if st.button(f"🚀 Procesar los {remaining} lotes restantes en segundo plano", type="primary"):
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                parser = BatchParser(batch_size=st.session_state.batch_size)
                verifier = MathematicalVerifier()
                
                for b_num in range(current_batch + 1, st.session_state.total_batches):
                    # Verificar si ya está en caché
                    if cache_manager.get_cached_batch(st.session_state.pdf_bytes, b_num, st.session_state.batch_size) is None:
                        status_text.text(f"Procesando lote {b_num + 1}...")
                        batch_data = parser.extract_batch(st.session_state.pdf_bytes, b_num, st.session_state.total_pages)
                        
                        v_results = []
                        for page_data in batch_data["pages"]:
                            formal_claims = llm_translate_to_z3(page_data["claims"])
                            p_results = [verifier.check_algebraic_identity(c["z3_code"], page_data["page_number"]) for c in formal_claims]
                            v_results.append({"page_number": page_data["page_number"], "results": p_results})
                        
                        cache_manager.save_batch_to_cache(st.session_state.pdf_bytes, b_num, st.session_state.batch_size, v_results)
                    
                    progress_bar.progress((b_num - current_batch) / remaining)
                
                status_text.text("✅ ¡Procesamiento completo!")
                st.success("Todos los lotes han sido procesados y almacenados en caché.")
                st.balloons()
