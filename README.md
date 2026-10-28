# MeuLauncher

Menu rapido (launcher) para Windows 10/11 com interface do tipo **Pie Menu**
(menu radial ao redor do cursor), aberto pela hotkey global **Ctrl+Espaco**.

## Como rodar

**Compilado (sem console, recomendado):**

```
dist\MeuLauncher.exe
```

Pode copiar o `MeuLauncher.exe` para qualquer pasta (ex: `C:\MeuLauncher\`)
ou na area de trabalho. Ele nao abre nenhuma janela de terminal.

**Via script (mostra console apenas em erros):**

```
pip install -r requirements.txt
pyw main.py
```

Para rodar sem console usando Python, use `pythonw.exe`:

```
pythonw.exe main.py
```

Um icone aparece na bandeja do sistema. Pressione `Ctrl+Espaco` (em qualquer
aplicativo) para abrir o menu na posicao do cursor.

## Controles

| Tecla/Mouse            | Acao                                  |
|------------------------|---------------------------------------|
| Ctrl+Espaco            | Abrir/fechar o menu                   |
| Movimento do mouse     | Navegar entre setores (hover)         |
| Clique esquerdo        | Abrir setor/submenu ou item           |
| Setas <- / ->          | Navegar entre setores (teclado)       |
| Numeros 1-8            | Selecionar setor por numero           |
| Enter                  | Confirmar selecao                     |
| Backspace              | Voltar ao anel anterior               |
| Esc / clique fora      | Fechar o menu                         |
| F2                     | Modo edicao (adicionar/remover favoritos) |

No modo edicao (F2): clique no centro para adicionar um app aos Favoritos.
Com o cursor sobre um favorito, pressione `Delete` para remove-lo.

## Setores

- **Busca**: pesquisa em tempo real no Menu Iniciar, area de trabalho e
  Program Files.
- **Favoritos**: apps configurados em `config.json`.
- **Ajustes**, **Painel**, **Tarefas**: utilitarios do Windows.
- **Desligar**: submenu com Reiniciar, Desligar e Sair (com confirmacao).
- **Suspender**, **Bloquear**: acoes rapidas do sistema.

## Configuracao

O arquivo `config.json` e criado automaticamente em:

```
%APPDATA%\MeuLauncher\config.json
```

Cores e estilo (tema padrao "Dark Glass"):

| Chave                          | Descricao                         | Padrao   |
|--------------------------------|-----------------------------------|----------|
| `colors.cor_fundo`             | Cor do fundo do circulo           | #0a0c10  |
| `colors.fundo_alpha`           | Opacidade do fundo (0-255)        | 175      |
| `colors.cor_borda`             | Cor da borda                      | #00d4ff  |
| `colors.cor_hover_inicio`      | Gradiente do setor em hover (inicio) | #2563eb |
| `colors.cor_hover_fim`         | Gradiente do setor em hover (fim) | #7c3aed  |
| `colors.cor_hover_alpha`       | Opacidade do hover (0-255)        | 205      |
| `colors.cor_texto`             | Cor do texto                      | #ffffff  |
| `colors.cor_glow`              | Cor do brilho/glow                | #00d4ff  |
| `colors.cor_setor_inativo`     | Cor dos setores sem hover         | #ffffff  |
| `colors.espessura_borda`       | Espessura da borda (px)           | 2        |
| `alpha`                        | Opacidade global do menu (0-1)    | 1.0      |
| `radius_inner` / `radius_outer`| Raios do anel principal           | 95 / 195 |
| `subradius_inner/outer`        | Raios do anel de submenus         | 205 / 285 |
| `hotkey`                       | Tecla de atalho global            | Ctrl+Espaco |
| `favorites`                    | Lista de apps favoritos           | -        |
| `sectors`                      | Quantidade de setores (max 8)     | 8        |

## Iniciar junto com o Windows

Na bandeja: **Iniciar com o Windows** (item marcavel). Ao marcar, o app cria a
entrada `MeuLauncher` em `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`
apontando para `pythonw.exe` (sem console) ou para o executavel compilado.

## Compilando em .exe

```
pip install pyinstaller
pyinstaller --noconsole --onefile --name MeuLauncher main.py
```

O binario fica em `dist\MeuLauncher.exe`. Apos compilar, o valor do registro
aponta para o proprio executavel automaticamente. Para rebuildar apos mudancas
no codigo, rode o mesmo comando novamente.

## Arquivos

- `main.py` - ponto de entrada, hotkey global, bandeja e autostart.
- `piemenu.py` - widget do menu radial (desenho, cores, transparencia, fade).
- `search.py` - indexacao e busca de programas.
- `config.py` - carregamento/salvamento do config.json.
- `system_actions.py` - acoes do sistema (desligar, suspender, etc.).
