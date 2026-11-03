# Gerenciador de Scripts para Windows

## Inicialização sob demanda (desenvolvimento)

Requer Windows 11 e Python com Tkinter instalado. Esta etapa usa o
`pythonw.exe` para abrir a interface sem console; a distribuição independente
de Python será tratada no empacotamento.

Execute `scripts/criar_atalho.ps1` uma única vez na configuração inicial de cada
computador/usuário. Ele apenas cadastra o atalho no Windows. Depois disso, o
Windows abre o programa diretamente pelo `.lnk` ao pressionar **Alt+C**;
o script PowerShell não é executado novamente durante o uso normal.

No PowerShell, a partir da raiz do projeto, informe o caminho real do interpretador:

```powershell
.\scripts\criar_atalho.ps1 -PythonwPath 'C:\caminho\Python\pythonw.exe'
```

O script cria `Gerenciador de Scripts.lnk` no menu Iniciar do usuário.
Pressione **Alt+C** para abrir a janela. Para escolher outra combinação:

```powershell
.\scripts\criar_atalho.ps1 -PythonwPath 'C:\caminho\Python\pythonw.exe' -Hotkey 'CTRL+ALT+J'
```

Escolha uma combinação livre de conflitos. O script não sobrescreve atalhos
existentes. Para alterar ou remover o gatilho, abra `shell:programs` pelo
Executar (`Win+R`) e edite as propriedades ou exclua o atalho.
Se mover o projeto ou o interpretador, atualize as propriedades do atalho ou
exclua o antigo e execute o script novamente na nova localização. A recriação
também é necessária se o atalho for apagado; para mudar apenas as teclas,
você pode editar suas propriedades.

O Windows gerencia o gatilho; nenhum processo do aplicativo precisa ficar
aberto esperando teclas. Fechar a janela pelo **X** encerra a aplicação.
A interface desta etapa serve apenas para validar a inicialização.

### Validação no Windows 11 Pro

1. Confirme que não existe uma instância do gerenciador aberta.
2. Pressione a combinação e confira a abertura sem console.
3. Feche pelo X e confira o encerramento no Gerenciador de Tarefas.
4. Repita com outra aplicação em foco.

### Resultado da validação

Em 03/11/2026, o usuário confirmou a abertura pelo gatilho **Alt+C** no
Windows 11 Pro e relatou tempo de abertura de **0,33 segundo** na versão de
desenvolvimento, executada com Python instalado. A medição relatada atende
à meta de até 1 segundo nesse teste.

O método de medição e as condições de inicialização a frio e carga não foram
informados. A validação nessas condições e no executável empacotado permanece
pendente. Captura de foco e inserção de scripts serão implementadas em etapas
posteriores.

## Domínio e casos de uso

`src/domain/` contém as entidades imutáveis `Pasta` e `Script`. A pasta de
sistema é protegida contra renomeação e exclusão. A edição de um script
preserva sua pasta. Unicidade, validação de textos vazios e limites de tamanho
continuam pendentes de definição; o conteúdo é preservado literalmente.

`src/application/` contém:

- `pasta.py`: `CasosDeUsoPastas`, com CRUD, inicialização de Geral e exclusão
  confirmada. `solicitar_exclusao()` fornece o aviso sobre a remoção dos scripts.
- `scripts.py`: `CasosDeUsoScripts`, com CRUD e consulta por pasta. O cadastro
  sem escolha de pasta utiliza Geral; uma pasta escolhida deve existir.
- `inserir_script.py`: `InserirScript`, com resultados de sucesso, falha ou
  ausência de destino válido. Apenas sucesso tem `deve_encerrar=True`.
- `contratos.py`: contratos de repositórios e inserção definidos com `Protocol`.
- `erros.py`: erros de entidade inexistente e confirmação ausente.

Os casos de uso recebem seus adaptadores pelo construtor. A inicialização do
banco em `main.py` já garante a existência de Geral. A listagem de pastas e o cadastro
na pasta padrão também garantem sua existência. O adaptador deve implementar
essa operação de forma idempotente, sem ID fixo nem identificação só pelo nome.

A interface deverá exibir o aviso de exclusão e passar `confirmado=True` somente
após confirmação explícita. O adaptador deverá excluir pasta e scripts atomicamente.
As operações de gerenciamento não solicitam encerramento. Após inserção, a
interface deverá encerrar somente quando `deve_encerrar` indicar sucesso.

O núcleo conta com adaptadores SQLite e testes de transações reais. A interface
atual continua sendo a janela de validação do gatilho; sua conexão com os casos
de uso e a integração Windows serão implementadas posteriormente. O adaptador de inserção deverá guardar o
destino anterior à abertura da janela e confirmar a inserção; enviar teclas
não comprova sucesso.

### Testes do núcleo

Na raiz do projeto, execute no PowerShell:

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
py -B -m unittest discover -s tests -v
```

Os testes do núcleo usam repositórios em memória e simulação da integração de
texto. Os testes de persistência usam arquivos SQLite temporários reais.
A inserção em aplicativos externos ainda depende da implementação Windows.

## Banco de dados SQLite

O banco usa `sqlite3`, da biblioteca padrão do Python, sem servidor ou instalação
adicional. Ao iniciar o programa, `main.py` chama `BancoDados().inicializar()`.
O arquivo é criado automaticamente em:

```text
%LOCALAPPDATA%\GerenciadorScripts\gerenciador.sqlite3
```

O caminho é resolvido para o usuário atual, sem nomes pessoais no código.
Mover a pasta do projeto não muda a localização dos dados. O construtor de
`BancoDados` também aceita um caminho explícito, usado nos testes isolados.

- `src/infraestructure/database.py`: caminho padrão, abertura e fechamento de
  conexões, criação do esquema, inicialização de Geral e controle transacional.
- `src/infraestructure/repository.py`: `RepositorioPastasSQLite` e
  `RepositorioScriptsSQLite`, implementando os contratos da aplicação e
  convertendo linhas do banco para entidades `Pasta` e `Script`.
- `tests/test_sqlite.py`: testes de integração da persistência real.

A tabela `pastas` guarda `id`, `nome` e `sistema` (0 ou 1). A tabela `scripts`
guarda `id`, `titulo`, `conteudo` e `pasta_id`, com associação obrigatória a uma
pasta existente. Todas as conexões habilitam `PRAGMA foreign_keys = ON`.
`ON DELETE CASCADE` remove os scripts junto da pasta; a confirmação continua
sendo exigida pelo caso de uso antes de chamar o repositório.

Geral é criada uma única vez, sem depender de ID fixo ou apenas do nome.
Um índice permite somente uma pasta de sistema, e gatilhos SQL impedem sua
alteração e exclusão. Pastas do usuário podem ter nomes repetidos, inclusive
Geral, e os títulos de scripts também podem se repetir.

Escritas usam `BEGIN IMMEDIATE`, com `commit` ao concluir e `rollback` em falhas.
As conexões são fechadas após cada operação. Consultas usam parâmetros para
preservar o conteúdo literal e evitar interpretar os textos como comandos SQL.
Arquivos SQLite e seus arquivos auxiliares estão ignorados pelo Git.

Foram executados **41 testes com sucesso** (21 do núcleo e 20 de SQLite), incluindo
CRUD, persistência após reabertura, concorrência na inicialização, proteção de
Geral, chaves estrangeiras, cancelamento, cascata, rollback e encerramento abrupto
de um processo com transação não confirmada. Os testes não simulam falha elétrica
nem substituem a validação final do aplicativo completo.

A inicialização atual cria o esquema de forma idempotente; não é um sistema de
migrações para futuras mudanças na estrutura do banco.

Referências: [sqlite3 no Python](https://docs.python.org/3.13/library/sqlite3.html)
e [chaves estrangeiras no SQLite](https://www.sqlite.org/foreignkeys.html).
