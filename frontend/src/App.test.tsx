import { render, screen } from '@testing-library/react';
import { expect, it } from 'vitest';
import App from './App';

it('explains the current milestone and read-only behavior', () => {
  render(<App />);
  expect(screen.getByRole('heading', { name: '磁盘快照' })).toBeTruthy();
  expect(screen.getByText(/不会修改、移动或删除/)).toBeTruthy();
  expect(screen.queryByRole('button', { name: /扫描/ })).toBeNull();
});
