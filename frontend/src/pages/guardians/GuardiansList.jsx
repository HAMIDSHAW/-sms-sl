import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { PageHeader, Table, Pagination, PhoneLink } from '../../components/ui'
import { api } from '../../lib/api'

export default function GuardiansList() {
  const [data, setData] = useState({ items: null, page: 1, pages: 1 })
  const [page, setPage] = useState(1)
  const navigate = useNavigate()

  useEffect(() => {
    api.get(`/api/guardians?page=${page}&per_page=15`).then(setData)
  }, [page])

  return (
    <div>
      <PageHeader eyebrow="Families" title="Guardians" description="Parents and guardians linked to your students." />
      <Table
        onRowClick={(r) => navigate(`/guardians/${r.id}`)}
        columns={[
          { key: 'full_name', header: 'Name', render: (r) => (
            <div className="flex items-center gap-2.5">
              <div className="w-7 h-7 rounded-full bg-sky/15 flex items-center justify-center text-[10px] font-display font-semibold text-sky shrink-0 overflow-hidden">
                {r.photo_url ? <img src={r.photo_url} alt="" className="w-full h-full object-cover" /> : `${r.first_name?.[0] || ''}${r.last_name?.[0] || ''}`}
              </div>
              <span className="font-medium">{r.full_name}</span>
            </div>
          ) },
          { key: 'phone', header: 'Phone', render: (r) => <PhoneLink value={r.phone} /> },
          { key: 'occupation', header: 'Occupation', render: (r) => r.occupation || 'N/A' },
          { key: 'address', header: 'Address', render: (r) => r.address || 'N/A' },
        ]}
        rows={data.items}
      />
      <Pagination page={data.page} pages={data.pages} onChange={setPage} />
    </div>
  )
}

