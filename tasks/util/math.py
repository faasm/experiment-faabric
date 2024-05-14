def cum_sum(ts, values):
    """
    Perform the cumulative sum of the values (i.e. integral) over the time
    interval defined by ts
    """
    assert len(ts) == len(values), "Can't CumSum over different sizes!({} != {})".format(len(ts), len(values))

    cum_sum = 0
    prev_t = ts[0]
    prev_val = values[0]
    for i in range(1, len(ts)):
        base = ts[i] - prev_t
        cum_sum += base * prev_val

        prev_t = ts[i]
        prev_val = values[i]

    # We discard the last value, but that is OK
    return cum_sum
