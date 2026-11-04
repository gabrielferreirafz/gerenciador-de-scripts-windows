# Gerenciador de Scripts para Windows

Ferramenta pessoal para organizar mensagens prontas em pastas e inserir o texto
no campo selecionado. Interface compacta escura, inspirada no histórico do Windows.

## MVP atual

O foco desta versão são os campos de mensagem do **Blip e WhatsApp Web no Chrome**.
Esses fluxos funcionaram nos testes manuais da implementação anterior. Esta versão
reaproveita essa implementação; a validação no seu ambiente continua necessária.
Não há garantia de funcionamento em todo campo de qualquer página. Pesquisa de
contatos do WhatsApp, assunto de e-mail e WhatsApp instalado ficam fora deste MVP.

O programa mantém um receptor leve em segundo plano. **Ctrl+Alt+Z** é registrado
pelo próprio receptor com `RegisterHotKey`; a espera é bloqueante (`GetMessageW`).
Não há monitoramento contínuo do foco, polling do teclado, nem banco ou Tkinter
abertos enquanto apenas o receptor está ocioso. A integração usa somente a
biblioteca padrão do Python, Win32 e UI Automation via `ctypes`.

## Configuração e uso no Windows 11

Requer Python com Tkinter instalado. Na raiz do projeto, execute no PowerShell:

```powershell
.\scripts\criar_atalho.ps1 -PythonwPath 'C:\caminho\Python\pythonw.exe' -IniciarComWindows -Iniciar
```

O script cria ou atualiza `Gerenciador de Scripts.lnk` no menu Iniciar do usuário,
fazendo uma cópia do atalho anterior em `%LOCALAPPDATA%\GerenciadorScripts\config`.
O `.lnk` inicia apenas o receptor e **não recebe uma combinação de teclas**:
isso evita a mudança de foco causada pelo antigo atalho do Explorer.
O parâmetro `-Iniciar` inicia o receptor imediatamente, sem console.
O parâmetro `-IniciarComWindows` também cria um atalho na pasta **Inicializar**
da conta atual. A partir do próximo logon, o Windows inicia somente o receptor,
sem console nem interface. Não é necessário executar o PowerShell a cada sessão
nem usar privilégios de administrador.

Depois da configuração:

1. O receptor inicia ao entrar na conta do Windows. Se você o encerrou manualmente,
   abra o gerenciador pelo menu Iniciar para iniciá-lo novamente.
2. Clique no campo de mensagem do Blip ou WhatsApp Web no Chrome.
3. Pressione **Ctrl+Alt+Z**, entre na pasta e clique no cartão do script.
4. O programa restaura o destino e cola o texto. **Não pressiona Enter nem envia mensagens.**

O menu de três pontos mantém **Ver script**, **Editar script** e **Excluir script**.
O conteúdo completo pode ser consultado em **Ver script** antes da inserção.
Fechar pelo **X**, ou clicar no script para inseri-lo, fecha somente a interface. O receptor
permanece disponível para o próximo Ctrl+Alt+Z. Repetir o atalho com a interface
aberta não cria outra janela nem substitui seu destino.

Para encerrar tudo, clique com o botão direito no ícone da bandeja e escolha
**Encerrar gerenciador**. Alternativamente:

```powershell
py -B src/main.py --encerrar
```

Executar o receptor outra vez não duplica a instância. Encerrá-lo pelo ícone da
bandeja encerra a sessão atual; no próximo logon, ele inicia novamente.
Ao mover o projeto ou o Python, encerre o receptor e execute novamente o script de
configuração na nova localização. Ele atualiza o atalho do menu Iniciar e também
o da inicialização, caso já esteja ativada. O script só configura os atalhos;
não é executado no logon nem em cada abertura da interface.

Para **desativar a inicialização automática**, pressione `Win+R`, abra
`shell:startup` e exclua somente `Gerenciador de Scripts.lnk`. Isso preserva o
atalho do menu Iniciar e os dados, e não encerra o receptor já em execução.
Para reativar, execute a configuração novamente com `-IniciarComWindows`.

Para validar, saia da conta e entre novamente (ou reinicie o computador): o ícone
deve aparecer na bandeja, sem abrir a interface. Clique no campo de mensagem e
pressione **Ctrl+Alt+Z**. A inicialização após reiniciar o computador foi validada
pelo usuário em 04/11/2026.

## Pastas e subpastas

Na lista inicial, **+ Nova pasta** cria uma pasta na raiz. Dentro de uma pasta,
**+ Subpasta** cria uma pasta filha e **+ Novo script** cadastra um script, com a
pasta atual selecionada como destino. Também é possível criar subpastas dentro
de outras subpastas. Cada nível pode conter nenhum ou vários scripts e subpastas.

Clique no cartão para entrar. A listagem mostra somente as subpastas e os scripts
diretos daquele nível, com as subpastas primeiro. O caminho aparece acima da lista;
**Voltar** sobe um nível, até retornar à raiz. Os mesmos menus de três pontos
permitem abrir, renomear e excluir pastas ou subpastas.

No cadastro de scripts, a seleção de pasta exibe o caminho completo, como
`Atendimento / Financeiro`. O script pertence a um único destino, que pode ser
uma pasta ou subpasta. Editar título/conteúdo continua preservando esse destino.
Nomes repetidos são diferenciados na seleção, sem expor IDs do banco.

Excluir uma pasta ou subpasta exige confirmação e remove seus descendentes e
todos os respectivos scripts na mesma transação. Geral continua protegida na
raiz e pode conter subpastas do usuário; essas subpastas podem ser renomeadas
ou excluídas normalmente.

O banco existente é atualizado automaticamente ao abrir a interface. A coluna
opcional `pastas.pai_id` referencia outra pasta com `ON DELETE CASCADE`;
as pastas anteriores permanecem na raiz, preservando IDs, nomes e scripts.
As restrições do banco impedem pais inexistentes e ciclos na hierarquia.

## Captura e inserção

Ao receber Ctrl+Alt+Z, o receptor captura a janela e a identidade do elemento com
foco **antes de abrir a interface**. Esses metadados passam ao processo da interface
por um pipe, sem arquivos temporários com conteúdo do campo. A interface revalida
esse destino e preserva texto e seleção antes de criar suas janelas.

A inserção usa texto Unicode na área de transferência e `SendInput` para Ctrl+V.
O conteúdo escolhido substitui somente a seleção capturada ou entra na posição do
cursor. O programa confere o destino antes da colagem. Ao clicar no script, a
interface é ocultada imediatamente e encerrada após a tentativa de envio de Ctrl+V,
sem reler o campo para confirmar a inserção nem aguardar seu resultado. O receptor
continua em segundo plano. O texto original salvo no banco permanece intacto;
a área de transferência passa a conter o script utilizado.

Se o destino mudou, foi fechado ou não expõe os recursos necessários, o programa
recusa a colagem e também fecha a interface. Não exibe confirmação de inserção
nem repete a colagem automaticamente. Confira o campo antes de reabrir e tentar
novamente. A ação **Inserir texto** na visualização completa segue o mesmo fluxo;
abrir pastas, visualizar e gerenciar scripts continuam mantendo a interface aberta.

## Organização do código

- `src/domain/`: entidades imutáveis `Pasta` e `Script`; proteção da pasta Geral.
- `src/application/`: CRUD, contratos, coordenação da inserção e identidade da sessão.
- `src/infraestructure/`: SQLite, repositórios, receptor do atalho, captura UIA e colagem Win32.
- `src/presentation/`: interface Tkinter/ttk, tema escuro e formulários.
- `src/main.py`: composição do receptor e da interface sob demanda.
- `scripts/criar_atalho.ps1`: configuração dos atalhos do menu Iniciar e da inicialização.
- `tests/`: testes de regressão do núcleo, persistência, interface e integração Windows.

O projeto não inclui páginas de captura, monitores de foco, logs de investigação
ou scripts experimentais. A interface conserva a navegação pastas → scripts,
cartões arredondados com prévia de tamanho fixo e os formulários de gerenciamento.

## Banco de dados

O SQLite é criado automaticamente ao abrir a interface:

```text
%LOCALAPPDATA%\GerenciadorScripts\gerenciador.sqlite3
```

O caminho usa o usuário atual, sem nomes pessoais no código. Mover o projeto não
move o banco. As conexões são fechadas após cada operação; escritas usam transações.
Chaves estrangeiras e `ON DELETE CASCADE` preservam os relacionamentos.
Geral é criada de forma idempotente e não pode ser renomeada nem excluída.
Excluir outra pasta exige confirmação e exclui seus scripts atomicamente.
O conteúdo textual é preservado literalmente; nomes e títulos podem se repetir.

## Testes e validação

Na raiz do projeto, execute:

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
py -B -W error::ResourceWarning -m unittest discover -s tests -v
```

Os testes usam bancos SQLite temporários e simulações das operações de colagem;
os testes de interface criam widgets Tk reais. Eles não enviam mensagens no Blip
ou WhatsApp e não substituem a validação manual desses serviços.

Para a validação manual, use um script fictício em um campo de mensagem sem enviar:
confira texto vazio, texto existente, seleção parcial, acentos, emoji e múltiplas
linhas. Confirme também reabertura após X/clique no script, ausência de janelas duplicadas e
encerramento pelo ícone da bandeja. A compatibilidade universal, o empacotamento e
a medição final de abertura/consumo ficam para etapas posteriores.
