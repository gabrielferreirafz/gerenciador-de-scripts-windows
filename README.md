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
