{#
  Fails if any combination of the given columns appears more than once.
  Used to enforce table grain, e.g. one row per track x region x date.
#}
{% test unique_combination(model, columns) %}

select
    {{ columns | join(', ') }},
    count(*) as row_count
from {{ model }}
group by {{ columns | join(', ') }}
having count(*) > 1

{% endtest %}
