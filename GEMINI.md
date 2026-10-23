# GEMINI.MD — Manual de Arquitetura e Engenharia do DocFAST

> **DocFAST** — Conversor e Editor Radial Instantâneo com Interface Liquid-Glass  
> **Desenvolvido por:** Gleisson Santos  
> **Repositório GitHub:** [https://github.com/corefusiion/DocFAST](https://github.com/corefusiion/DocFAST)  
> **Website Oficial:** [https://docfastbr.lovable.app/](https://docfastbr.lovable.app/)  
> **Versão:** 1.1.0 PRO  

---

## 1. Visão Geral do Projeto

O **DocFAST** é uma aplicação desktop de alta performance para **Windows, macOS e Linux** que revoluciona o fluxo de manipulação de documentos, planilhas e imagens. 

Ao invés de exigir a inicialização de suítes de escritório pesadas ou o upload de dados confidenciais para servidores em nuvem, o DocFAST detecta quando o usuário está arrastando um ou múltiplos arquivos e, ao pressionar uma tecla de gatilho (como `Shift`), projeta um **menu radial translúcido (liquid-glass)** sob o cursor. A soltura sobre qualquer fatia realiza a conversão ou dispara a ferramenta de edição selecionada em segundo plano.

---

## 2. Tecnologias e Dependências Principais

* **Linguagem:** Python 3.11+
* **Framework Gráfico:** **PySide6 (Qt 6.7+)** — Aceleração por hardware, gráficos vetoriais, sistema de coordenadas High-DPI.
* **Manipulação de Documentos PDF:** **PyMuPDF (`fitz`)** — Alta velocidade na renderização, extração vetorial, injeção de carimbos/assinaturas e reorganização de páginas.
* **Processamento de Imagens:** **Pillow (PIL)** — Transformações, corte, filtragem, geração de transparência e mesclagem alfa.
* **Manipulação de Planilhas:** **openpyxl** — Leitura e conversão nativa de pastas de trabalho Excel (`.xlsx`, `.xls`) para PDF, CSV, JSON e HTML.
* **Efeitos Visuais e Composição:**
  * Windows 10/11: **Windows Acrylic Blur-Behind (`SetWindowCompositionAttribute`)** e DWM API.
  * Shaders e Renderização Procedural: Campo de Distâncias Assinadas (**SDF**) e dispersão de refração cromática em tempo real (`liquid.py` e `glass.py`).
* **Empacotamento:** **PyInstaller** (`DocFAST.spec`) e **Inno Setup** (`installer/DocFAST.iss`).

---

## 3. Arquitetura de Módulos (`docfast/`)

```
docfast/
├── __init__.py           # Versão da aplicação (1.1.0)
├── app.py                # Ponto central da aplicação, loop Qt, tray icon, toasts, orquestrador
├── radial.py             # Menu radial circular translúcido, detecção angular, física de mola
├── convert.py            # Motor de conversão (Imagens, PDF, Planilhas, DOCX, TXT)
├── pdf_tools.py          # Ferramentas avançadas de PDF (Assinatura/Carimbo e Organizador de Páginas)
├── snipper.py            # Ferramenta de Captura de Tela (PrintScreen) e Integração com Clipboard
├── tools.py              # Janelas de edição (Recortar, Anotar, Tarjar, Compactar, Redimensionar, Fundo)
├── glass.py              # Efeito visual Liquid-Glass, captura de fundo, sombras e borda arco-íris
├── liquid.py             # Renderização matemática SDF (Signed Distance Fields) e refração
├── toasts.py             # Sistema de notificações translúcidas com ações (Abrir, Mostrar na Pasta, Desfazer)
├── i18n.py               # Sistema de internacionalização dinâmico (Português PT-BR e Inglês EN)
├── trigger.py            # Gancho de teclado/mouse (Global keyboard watcher)
├── handoff.py            # IPC de inicialização em microssegundos (Named Pipes no Windows / UNIX sockets)
├── settings.py           # Gerenciamento de configurações e janelas de Preferências e Boas-vindas
├── report.py             # Formatação de relatórios de conclusão de tarefas
└── util.py               # Utilitários de sistema de arquivos, formatação de bytes e fontes
```

---

## 4. Detalhamento dos Componentes Chave

### 4.1. Comunicação Interprocesso Instantânea (`handoff.py`)
Quando o usuário aciona o DocFAST pelo menu de contexto do Windows Explorer (*"Enviar para → DocFAST"* ou clique com botão direito), o sistema **não** inicializa uma segunda instância pesada do Qt.
1. `try_handoff(sys.argv)` é executado nos primeiros 10ms do `run.py`.
2. Conecta-se diretamente ao Named Pipe `\\.\pipe\DocFAST-<username>` criado pela instância ativa.
3. Transmite a lista de arquivos via JSON e encerra o processo imediatamente (`sys.exit(0)`).
4. A instância ativa recebe a notificação pelo `QLocalServer` e abre o menu sob o cursor em milissegundos.

### 4.2. Motor de Conversão (`convert.py`)
* **Planilhas (`.xlsx`, `.xls`, `.csv`)**:
  * Exporta para PDF gerando tabelas formatadas com cabeçalhos destacados e larguras de coluna proporcionais calculadas via PyMuPDF.
  * Exporta para JSON estruturado com chave/valor linha a linha.
  * Exporta para tabelas HTML com estilos modernos e limpos.
* **Lote de Imagens**:
  * `PDF (1 doc)`: Agrupa múltiplas imagens selecionadas em um único PDF sequencial.
  * `PDF (sep)`: Converte cada imagem individualmente para seu respectivo PDF independente.
  * Conversão de formatos universais: JPG, PNG, WEBP, AVIF, HEIC, TIFF, BMP, ICO.

### 4.3. Ferramentas Avançadas de PDF (`pdf_tools.py`)
* **`SignPdfWindow`**:
  * **Remoção de Fundo (`make_signature_transparent`)**: Analisa o limiar de brilho de cada pixel do carimbo/rubrica e transforma o papel branco/cinza em canal alfa 100% transparente, preservando o traço da caneta.
  * **`SignaturePadDialog`**: Permite desenhar livremente com mouse ou stylus vetorial. Converte a assinatura diretamente para memória através de `glass.pil_from_qimage` sem escrita temporária em disco.
  * **Injeção de Carimbo no PDF**: Utiliza `fitz.Page.insert_image` calculando as coordenadas normalizadas (0.0 a 1.0) para posicionar a assinatura com resolução preservada.
  * **Opções de Salvamento**: Opção de salvar diretamente como `(Assinado).pdf` ou abrir a caixa de diálogo nativa do Windows Explorer (`Salvar Como…`).
* **`OrganizePdfWindow`**:
  * Grade interativa de miniaturas das páginas com reordenação por arrasto (Drag & Drop).
  * Botões de rotação individual de 90° e exclusão de páginas em branco.

### 4.4. Captura de Tela e Integração com Clipboard (`snipper.py`)
* **`ScreenSnipper`**:
  * Cobre a geometria virtual de todos os monitores conectados.
  * Escurece o desktop preservando a área de seleção com moldura azul e indicador de dimensões em tempo real.
  * Mapeia coordenadas normalizadas para suportar monitores com High-DPI (escalas de 125%, 150%, 200%).
* **`SnipActionDialog`**:
  * Diálogo instantâneo para salvar o recorte em PNG, JPG, PDF, copiar para o clipboard ou enviar para a ferramenta de anotações e setas.

---

## 5. Procedimentos de Build e Compilação

### Ambiente de Desenvolvimento:
```bash
# Ativação do ambiente virtual
.\.venv\Scripts\Activate.ps1

# Instalação das dependências
pip install -r requirements.txt
```

### Execução de Testes:
```bash
# Execução completa da suíte de testes
python -m pytest -v

# Auto-teste interno do executável
python run.py --selftest
```

### Compilação do Executável com PyInstaller:
```bash
# Gera o executável em dist\DocFAST\DocFAST.exe
.\.venv\Scripts\pyinstaller.exe DocFAST.spec --noconfirm
```

---

## 6. Créditos e Responsabilidade

* **Idealização e Desenvolvimento:** **Gleisson Santos**
* **Portal de Distribuição e Doações:** [https://docfastbr.lovable.app/](https://docfastbr.lovable.app/)
* **Licença de Uso:** MIT License
