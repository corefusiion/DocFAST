<div align="center">

![DocFAST Banner](docs/banner.png)

# DocFAST PRO
### Sistema Radial Instantâneo de Conversão, Automação e Inteligência Artificial
*Manipulação ultrarrápida de documentos, dados, PDFs e imagens com interface Liquid-Glass para Windows, macOS e Linux.*

---

[![Status da Build](https://img.shields.io/github/actions/workflow/status/corefusiion/DocFAST/build.yml?branch=main&style=flat-square&label=Build%20Windows&logo=github&color=2563EB)](https://github.com/corefusiion/DocFAST/actions)
[![Versão](https://img.shields.io/badge/versão-1.1.0--PRO-0EA5E9?style=flat-square)](https://github.com/corefusiion/DocFAST/releases/latest)
[![Python](https://img.shields.io/badge/python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Licença](https://img.shields.io/badge/licença-MIT-10B981?style=flat-square)](LICENSE)
[![Plataformas](https://img.shields.io/badge/plataformas-Windows%20%7C%20macOS%20%7C%20Linux-64748B?style=flat-square)]()

<br>

<p align="center">
  <a href="https://ko-fi.com/corefusion">
    <img src="https://img.shields.io/badge/Apoiar%20no%20Ko--fi-Verde%20%E2%99%A5-00b977?style=for-the-badge&logo=kofi&logoColor=white" alt="Apoiar no Ko-fi">
  </a>
  &nbsp;&nbsp;
  <a href="https://docfastbr.lovable.app/">
    <img src="https://img.shields.io/badge/Portal%20Oficial-DocFAST-2563EB?style=for-the-badge&logo=google-chrome&logoColor=white" alt="Portal Oficial">
  </a>
</p>

<br>

[Visão Geral](#-visão-geral) • [Recursos Centrais](#-recursos-centrais) • [Atalhos Globais](#-atalhos-e-gestos-de-produtividade) • [Matriz de Dados e Formatos](#-matriz-completa-de-conversões) • [Instalação](#-instalação-e-download) • [Créditos](#-créditos-e-licença)

---

</div>

## ⬡ Visão Geral

O **DocFAST** revoluciona o fluxo de manipulação de arquivos no trabalho corporativo. Em vez de depender de suítes de escritório lentas ou serviços de nuvem arriscados, o DocFAST opera **100% localmente com aceleração gráfica**.

Basta começar a arrastar qualquer arquivo, pasta ou imagem da web e pressionar a tecla de gatilho (`Shift`, `Ctrl` ou `Alt`): um **menu radial translúcido em estilo Liquid-Glass** surge sob o cursor do mouse. Ao soltar sobre a fatia correspondente, a operação é executada em milissegundos em segundo plano.

```
Arrastar Arquivo ──▶ Pressionar [Shift] ──▶ Menu Radial Projetado ──▶ Soltar na Ação ──▶ Concluído em ms
```

---

## ✦ Recursos Centrais

### 1. 🤖 Assistente Multimodal Liquid AI & Auditor de Fórmulas Excel (`Ctrl + 3`)
* **Auditor de Planilhas Instantâneo (`Ctrl + 3`):** Pressione `Ctrl + 3` sobre qualquer tabela ou tela do Excel. O DocFAST captura a tabela e abre o chat de IA especializado explicando fórmulas complexas (`PROCX`, `IFS`, `SOMASES`), sugerindo correções e apontando inconsistências de dados.
* **Ajuda AI Multimodal Onipresente:** Selecione qualquer texto em sistemas legados, navegadores ou ERPs e acione com 1 clique. Fixe a janela (📌) ao lado da sua tela enquanto continua navegando.
* **Multi-Provedor de IA de Ponta:** Suporte nativo para **Google Gemini** (`gemini-2.5-flash`, `gemini-2.5-pro`), **OpenAI** (`gpt-4o`, `o3-mini`), **Anthropic Claude** (`claude-3-7-sonnet`) e **LLMs Locais / Ollama / OpenCode** para empresas sem conexão com a internet.

---

### 2. 🔀 Conversor Universal de Dados Estruturados (*Data Matrix*)
Converta bidirecionalmente arquivos de dados estruturados com formatação profissional em segundos:
* **Formatos Suportados:** `JSON` ↔ `CSV` ↔ `TSV` ↔ `YAML` ↔ `XML` ↔ `Planilhas XLSX (Excel)` ↔ `Tabelas Markdown (MD)`.
* **Geração de Excel Formatado:** Converte JSON ou CSV para `.xlsx` com cabeçalho corporativo em azul navy, texto em Segoe UI, bordas suaves e largura de colunas autoajustável.
* **Tabelas Markdown:** Arraste um CSV ou XLSX e gere tabelas Markdown perfeitamente alinhadas para documentações técnicas ou GitHub.

---

### 3. 📂 Pastas Monitoradas (*Watch Folders*)
* **Automação Contínua em Segundo Plano:** Cadastre pastas monitoradas (ex: `C:\Downloads\Notas` ou pastas compartilhadas da rede).
* **Conversão Passiva Silenciosa:** Qualquer arquivo que chega na pasta é automaticamente convertido para o formato escolhido (ex: `PDF`, `PNG`, `CSV`) com notificação discreta na tela.
* **Ação Pós-Processamento:** Escolha entre manter o original, arquivar em subpasta `_processados` ou mover com segurança para a Lixeira.

---

### 4. 🌐 Arrastar Imagens Direto do Navegador Web (*Web Drag & Drop*)
* **Sem Necessidade de Salvar Primeiro:** Arraste fotos, gráficos ou links do Google Chrome, Microsoft Edge ou Firefox segurando `Shift`.
* O DocFAST faz o download seguro para cache temporário e projeta o menu de conversão na hora, salvando o arquivo já convertido no seu Desktop ou pasta Downloads.

---

### 5. 📈 Painel de Conversões Recentes & Economia de Disco (*Activity Hub*)
* **Histórico Visual com Miniaturas:** Acompanhe os últimos 50 arquivos convertidos no painel Liquid-Glass.
* **Métricas Reais de Redução:** Visualize o tamanho original vs final e o percentual de espaço economizado em disco (ex: `-74% menor`).
* **Ações Imediatas:** Botões diretos para `👁️ Abrir Arquivo`, `📁 Mostrar na Pasta` e `📋 Copiar para Área de Transferência`.

---

### 6. 📋 Histórico Visual da Área de Transferência (`Ctrl + Alt + V`)
* Painel translúcido de vidro reunindo os últimos 25 itens copiados (textos, códigos, imagens com miniaturas e tabelas formatadas).
* Busca em tempo real e colagem com 1 clique, evitando perda de informações copiadas durante o dia.

---

### 7. 📝 Notas Rápidas Fixas de Vidro (*Sticky Notes Corporativo*)
* Lembretes translúcidos elegantes fixados na tela com múltiplas paletas (Aurora, Menta, Amarelo Solar, Ardósia e Rosa).
* Inicialização inteligente: restaura no máximo 1 nota na abertura para manter sua área de trabalho limpa e produtiva.

---

### 8. 🔏 Assinador com Certificado Digital ICP-Brasil (A1 / PAdES)
* Assine contratos e laudos técnicos em PDF com certificado digital padrão ICP-Brasil (`.pfx` ou A1).
* Aplica carimbo oficial contendo dados do titular, autoridade certificadora emissora, data/hora e hash criptográfico SHA-256 com validade jurídica.

---

### 9. 🎞️ Gravador de Tela para GIF Otimizado (até 15s)
* Selecione qualquer área da tela e grave pequenos tutoriais, demonstrações de bugs ou passos para colegas de trabalho.
* Gera automaticamente GIFs leves (< 2 MB) a 10 FPS salvos diretamente na Área de Trabalho.

---

### 10. 📡 Comunicados em Rede Local (*DSS & Alertas P2P*)
* Envie comunicados de segurança (Diálogo Semanal de Segurança - DSS) e avisos da equipe para todos os computadores da mesma rede corporativa via broadcast UDP, sem depender de servidores dedicados.
* Notificação elegante em vidro ancorada próxima ao relógio do Windows com permanência de até 2 minutos ou fechamento voluntário.

---

### 11. 🗑️ Substituição Segura na Lixeira & Regra "Only If Smaller"
* **Safe Recycle Bin:** Opção nas preferências para substituir o arquivo original enviando-o com segurança para a Lixeira do Windows (com direito a `Ctrl+Z`), sem acionar alertas de antivírus.
* **Only if Smaller:** Em compressões e conversões, descarta o resultado caso ele fique maior que o arquivo original.

---

## ⚡ Atalhos e Gestos de Produtividade

| Ação | Atalho / Gesto | Descrição |
| :--- | :--- | :--- |
| **Menu Radial Principal** | `Arrastar + Shift` | Projeta o menu de conversões e ferramentas sob o cursor |
| **Alternar Anéis** | Toque duplo em `Shift` | Alterna entre anel de formatos e ferramentas visuais |
| **Auditor de Planilhas IA** | `Ctrl + 3` | Captura a tela da tabela e abre a IA com foco em Excel |
| **Histórico da Área de Transferência** | `Ctrl + Alt + V` | Abre o painel Liquid-Glass com os últimos 25 itens copiados |
| **Botão Direito do Mouse** | Menu do Windows Explorer | Acesso nativo a "Menu Radial", "Ajuda AI" e "Compactar Zip" |

---

## 📊 Matriz Completa de Conversões

| Categoria | Formatos de Entrada | Formatos de Saída Disponíveis |
| :--- | :--- | :--- |
| **Dados Estruturados** | `JSON`, `CSV`, `TSV`, `YAML`, `YML`, `XML` | `XLSX (Excel)`, `CSV`, `JSON`, `YAML`, `XML`, `Markdown Table`, `PDF` |
| **Planilhas Corporativas** | `XLSX`, `XLS`, `CSV`, `XLSM`, `XLSB`, `TSV` | `PDF formatado`, `CSV`, `JSON`, `HTML`, `Extrair Mídias` |
| **Imagens Universais** | `PNG`, `JPG`, `WEBP`, `AVIF`, `HEIC`, `TIFF`, `BMP`, `ICO`, `GIF` | Qualquer formato listado, `PDF (1 doc)`, `PDF (separados)` |
| **Documentos PDF** | `PDF` | `JPG`, `PNG`, `DOCX`, `TXT`, `Assinar ICP-Brasil`, `Organizar Páginas` |
| **Documentos Word** | `DOCX` | `PDF`, `TXT`, `Extrair Mídias Embutidas` |
| **Textos & Markdown** | `TXT`, `MD`, `LOG`, `HTML` | `PDF`, `DOCX`, `Markdown formatado` |
| **Arquivos & Pastas** | Qualquer arquivo ou diretório | `Zip (Rápido)`, `Zip (Máximo 9)`, `Extrair` |

---

## 📥 Instalação e Download

Baixe a versão mais recente diretamente na página de [Releases Oficiais](https://github.com/corefusiion/DocFAST/releases/tag/latest):

* **[Download: DocFAST-Setup.exe (Instalador Oficial)](https://github.com/corefusiion/DocFAST/releases/download/latest/DocFAST-Setup.exe)**  
  *Instalação limpa por usuário (não precisa de direitos de administrador). Cria atalhos no Menu Iniciar, Botão Direito e Enviar Para.*
* **[Download: DocFAST.exe (Versão Portátil)](https://github.com/corefusiion/DocFAST/releases/download/latest/DocFAST.exe)**  
  *Executável único standalone: não precisa de instalação, basta baixar e rodar de qualquer pasta ou pendrive.*

---

## 🛠️ Execução e Compilação

Para executar em ambiente de desenvolvimento:

```powershell
# Clonar o repositório
git clone https://github.com/corefusiion/DocFAST.git
cd DocFAST

# Ativar o ambiente virtual e instalar dependências
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Executar o DocFAST
python run.py

# Executar a suíte completa de testes unitários
python -m pytest -v
```

---

## 🤝 Créditos e Licença

* **Idealização e Desenvolvimento:** **Gleisson Santos**
* **Apoio ao Projeto:** [Ko-fi CoreFusion](https://ko-fi.com/corefusion)
* **Portal Oficial:** [https://docfastbr.lovable.app/](https://docfastbr.lovable.app/)
* **Licença de Uso:** Licença MIT — Código aberto para a comunidade.
