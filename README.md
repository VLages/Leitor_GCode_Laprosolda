# Como Rodar o Programa

Olá, Rosa.

Para visualizar o estágio atual do software, é necessário baixar os dois arquivos: “main.py” e “editor_grafico.py” (é importante que ambos estejam na mesma pasta). Em seguida, abra o arquivo “main.py” em um editor de texto (estou utilizando o VSCode) e execute-o normalmente, clicando no botão localizado no canto superior direito, “Run Python File”.

## Dia 1

Hoje, foquei principalmente em compreender o funcionamento do QT Designer. Como resultado, desenvolvi apenas um rascunho inicial de como desejo que o programa se apresente em sua versão final.

Ao abrir o programa, você verá duas caixas brancas:

- A mais estreita, localizada à esquerda, será destinada à exibição do GCode, sendo possível editá-lo diretamente no programa;

- A caixa maior, à direita, será responsável pela visualização do desenho.

Os botões posicionados no rodapé terão as mesmas funções dos botões do NCViewer, porém adaptados para atender às nossas especificações.

## Dia 2

Neste dia, encontrei um vídeo de um desenvolvedor estrangeiro criando um modelo simples de uma engine 3D em Python (https://www.youtube.com/watch?v=M_Hx0g5vFko), utilizando as bibliotecas Pygame, NumPy e Numba. A partir disso, concentrei meus esforços em compreender o funcionamento dessa engine, com o objetivo de adaptá-la e implementá-la em nosso software. 

Em relação ao desenvolvimento do programa, foram realizadas algumas melhorias estruturais e funcionais. Inicialmente, reorganizei a disposição dos arquivos, visando facilitar a visualização das tarefas pendentes e melhorar a organização do projeto. Além disso, iniciei a implementação de matrizes e projeções matemáticas, que serão fundamentais para a geração e exibição de objetos em 3D.

Por fim, o botão de “Tela Cheia” foi implementado e encontra-se funcionando corretamente.