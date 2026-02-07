import { useState, FormEvent } from 'react';
import { api } from '../../hooks/useApi';

interface Props {
  groupId: string;
  onSaved: () => void;
  onCancel: () => void;
}

export default function CategoryForm({ groupId, onSaved, onCancel }: Props) {
  const [name, setName] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setLoading(true);
    try {
      await api.createCategory({ name: name.trim(), group_id: groupId });
      onSaved();
    } catch (err: any) {
      alert(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <form className="inline-form category-add-form" onSubmit={handleSubmit}>
      <input
        type="text"
        value={name}
        onChange={e => setName(e.target.value)}
        placeholder="Category name"
        autoFocus
        disabled={loading}
      />
      <button type="submit" className="btn btn-primary btn-sm" disabled={loading || !name.trim()}>
        Add
      </button>
      <button type="button" className="btn btn-ghost btn-sm" onClick={onCancel}>
        Cancel
      </button>
    </form>
  );
}
