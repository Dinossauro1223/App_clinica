'use strict';
const fs = require('node:fs');
const vm = require('node:vm');
const test = require('node:test');
const assert = require('node:assert/strict');

const html = fs.readFileSync('mobile/static/index.html', 'utf8');
const match = html.match(/\/\/ BEGIN OFFLINE MAP CONFLICT HELPERS[\s\S]*?\/\/ END OFFLINE MAP CONFLICT HELPERS/);
assert.ok(match, 'helpers de conflito offline devem estar presentes no app');
const helpers = vm.runInNewContext(match[0] +
  '\n;({idsMapa,baseCompletaMapa,contarConflitosMapa})');
const snap = row => JSON.stringify({id_leito: row.id_leito, nome: row.nome || ''});
const base = {
  '1': {id_leito: 1, nome: 'Ana'},
  '2': {id_leito: 2, nome: 'Bia'},
  '3': {id_leito: 3, nome: ''},
};

test('alteração concorrente em leito existente é detectada', () => {
  const atual = [base['1'], {...base['2'], nome: 'Beatriz'}, base['3']];
  assert.equal(helpers.contarConflitosMapa(base, atual, snap), 1);
});
test('inclusão concorrente de leito é detectada', () => {
  const atual = [...Object.values(base), {id_leito: 4, nome: 'Caio'}];
  assert.equal(helpers.contarConflitosMapa(base, atual, snap), 1);
});
test('remoção concorrente de leito é detectada', () => {
  const atual = [base['1'], base['3']];
  assert.equal(helpers.contarConflitosMapa(base, atual, snap), 1);
});
test('mudanças combinadas contam inclusão, remoção e alteração sem duplicar leito ausente', () => {
  const atual = [{...base['1'], nome: 'Ana Maria'}, {id_leito: 4, nome: 'Caio'}];
  assert.equal(helpers.contarConflitosMapa(base, atual, snap), 4);
});
test('base offline incompleta nunca autoriza envio automático', () => {
  assert.equal(helpers.baseCompletaMapa({linhas: [base['1'], base['2']]}, base), false);
  assert.equal(helpers.baseCompletaMapa({linhas: Object.values(base)}, null), false);
  assert.equal(helpers.baseCompletaMapa({linhas: Object.values(base)}, base), true);
});
